import sys
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ensure imports work
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from neo4j import GraphDatabase
import requests
from src.core.api_client import BackendClient
from src.nlp.gazette_neo4j_ingester import GazettePatternDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("GAZETTE_AGGREGATOR")

class GazetteAggregatorWorker:
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687", 
                 neo4j_user: str = "neo4j", 
                 neo4j_password: str = "admin123"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.backend = BackendClient()
        self.backend_public_url = "http://localhost:8080/api/v1/politicians"

    def close(self):
        self.driver.close()

    def get_all_politicians(self) -> List[Dict[str, Any]]:
        """Fetch all politicians from the backend via the public search API."""
        try:
            resp = requests.get(f"{self.backend_public_url}/search?name=", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch politicians from backend: {e}")
            return []

    def run(self, limit: int = 100):
        logger.info(f"🚀 Starting Gazette Aggregator Worker (Limit: {limit})...")
        politicians = self.get_all_politicians()
        
        if not politicians:
            logger.warning("No politicians found to process.")
            return

        with self.driver.session() as session:
            detector = GazettePatternDetector(neo4j_session=session)
            
            processed = 0
            for pol in politicians[:limit]:
                pol_id = pol.get("id")
                external_id = pol.get("externalId")
                name = pol.get("name")
                
                if not external_id:
                    continue
                
                logger.info(f"  🔍 Analyzing Gazette links for {name} ({external_id})...")
                
                # Use the detector to find links in Neo4j
                links = detector.detect_politician_cnpj_link(external_id, session=session)
                
                if not links:
                    logger.info(f"    No gazette links found for {name}.")
                    continue
                
                # Aggregate findings into the format expected by the frontend
                findings = []
                total_score = 0
                
                for link in links:
                    # Map Neo4j link results to Frontend-friendly structure
                    # Link structure from detector: {politico, cnpj, empresa, modalidade, valor, processo, grau}
                    finding = {
                        "empresa": link.get("empresa") or link.get("empresa_destino") or "Empresa Desconhecida",
                        "cnpj": link.get("cnpj") or link.get("cnpj_destino") or "N/A",
                        "valor": f"R$ {link.get('valor', 0):,.2f}",
                        "modalidade": link.get("modalidade", "DISPENSA"),
                        "city": "N/A", # Territory not always in the link record, but in DiarioOficial node
                        "date": "2024-2025",
                        "score": 85 if link.get("grau") == "DIRETO" else 65 if link.get("grau") == "2º GRAU" else 45
                    }
                    findings.append(finding)
                    total_score = max(total_score, finding["score"])

                # Update the politician in the backend
                update_payload = {
                    "externalId": external_id,
                    "nlpGazetteCount": len(findings),
                    "nlpGazetteScore": total_score,
                    "nlpGazetteDetails": json.dumps(findings)
                }
                
                logger.info(f"    Found {len(findings)} links. Sending to backend...")
                self.backend.ingest_politician(update_payload)
                processed += 1

        logger.info(f"✅ Gazette Aggregation complete. Processed {processed} politicians with findings.")

if __name__ == "__main__":
    worker = GazetteAggregatorWorker()
    try:
        worker.run(limit=1000)
    finally:
        worker.close()
