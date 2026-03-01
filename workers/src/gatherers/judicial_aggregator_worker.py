import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import json
import requests
from typing import Dict, Any, List
from src.core.api_client import BackendClient
from src.loaders.datajud_loader import DataJudLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JUDICIAL_AGGREGATOR")

class JudicialAggregatorWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.loader = DataJudLoader()

    def get_all_politicians(self) -> List[Dict[str, Any]]:
        """Fetches all politicians from the backend search API."""
        try:
            url = "http://localhost:8080/api/v1/politicians/search?name="
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Failed to fetch politicians: {e}")
            return []

    def run(self, limit: int = 100):
        logger.info(f"🚀 Starting Judicial Aggregator Worker (Limit: {limit})...")
        
        politicians = self.get_all_politicians()
        if not politicians:
            logger.warning("No politicians found for analysis.")
            return

        processed_count = 0
        findings_count = 0

        for pol in politicians[:limit]:
            name = pol.get("name")
            ext_id = pol.get("externalId")
            
            if not name or not ext_id:
                continue

            logger.info(f"  ⚖️ Checking judicial records for {name} ({ext_id})...")
            
            try:
                # Query DataJud
                risk_data = self.loader.build_judicial_risk_score(name)
                
                score = risk_data.get("risk_score", 0)
                details = json.dumps(risk_data.get("processes", []), ensure_ascii=False)
                
                # Update Backend
                self.backend.ingest_politician({
                    "externalId": ext_id,
                    "name": name,
                    "judicialRiskScore": score,
                    "judicialRiskDetails": details
                })
                
                if score > 0:
                    findings_count += 1
                    logger.info(f"    🚨 Finding! Score: {score}")
                else:
                    logger.info("    ✅ No relevant records found.")
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"  ❌ Error processing {name}: {e}")

        logger.info(f"✅ Judicial Aggregation complete. Processed {processed_count} politicians. Findings: {findings_count}")

if __name__ == "__main__":
    worker = JudicialAggregatorWorker()
    worker.run(limit=100)
