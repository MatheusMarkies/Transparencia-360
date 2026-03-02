"""
RAIS Worker - The "Ghost Employee Hunter".
Processes massive labor repository dumps to find if political staff have other incompatible jobs.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import polars as pl
import os
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAISWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.data_dir = Path("data/raw/rais")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def process_dump(self, csv_path: str):
        """Processes a RAIS CSV dump using Polars (Caixa Fria)."""
        logger.info(f"Processing RAIS dump: {csv_path}")
        
        try:
            # RAIS files are notoriously large and often use fixed-width or specific delimiters
            # For this implementation, we assume a CSV-like structure with semicolon
            df = pl.read_csv(csv_path, separator=";", encoding="latin-1", infer_schema_length=1000)
            
            # Identify columns (these names vary by year/release)
            # Common ones: 'CPF', 'Nome', 'Vl Remun Média (RS)', 'Qtd Horas Contrat'
            
            logger.info(f"  Read {len(df)} records from RAIS")
            
            # Filtering criteria for anomalies:
            # 1. Very high salaries in remote locations
            # 2. Duplicate CPFs in different states (if we have staff data to join)
            
            # For now, we'll just demonstrate Polars aggregation
            # In a real scenario, we'd join with workers/src/gatherers/staff_anomaly_worker.py data
            
            summary = df.group_by("Município").agg([
                pl.len().alias("count"),
                pl.col("Vl Remun Média (RS)").mean().alias("avg_salary")
            ]).sort("count", descending=True)
            
            logger.info("  RAIS Summary by Municipality computed successfully.")
            return summary
            
        except Exception as e:
            logger.error(f"Error processing RAIS: {e}")
            return None

    def run(self):
        logger.info("=== RAIS Worker - Ghost Employee Hunter starting ===")
        # Look for downloaded files
        files = list(self.data_dir.glob("*.csv"))
        if not files:
            logger.warning(f"No RAIS CSV files found in {self.data_dir}. Please place dumps there.")
            return

        for f in files:
            self.process_dump(str(f))

if __name__ == "__main__":
    worker = RAISWorker()
    worker.run()
