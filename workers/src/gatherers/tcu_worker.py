"""
TCU Worker - Monitoring Irregular Accounts.
Integrates with Tribunal de Contas da União open data.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import polars as pl
import requests
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TCUWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.base_url = "https://dadosabertos.tcu.gov.br/api/rest/v2"

    def fetch_ineligible_list(self):
        """Fetches the list of individuals with irregular accounts."""
        logger.info("Fetching TCU irregular accounts list...")
        
        # Example endpoint - check actual documentation for latest REST v2 paths
        url = f"{self.base_url}/contas-irregulares"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if data:
                df = pl.DataFrame(data)
                logger.info(f"  Found {len(df)} records in TCU database")
                
                # Filter for high-risk profiles if needed
                # Ingest into backend for cross-matching
                for row in df.limit(10).to_dicts():
                    logger.info(f"  TCU Alert: {row.get('nome')} - {row.get('cpf')}")
                
                return df
        except Exception as e:
            logger.error(f"Error in TCUWorker: {e}")
            return None

    def run(self):
        self.fetch_ineligible_list()

if __name__ == "__main__":
    worker = TCUWorker()
    worker.run()
