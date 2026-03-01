import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
from src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CamaraGatherer:
    def __init__(self):
        # Base URL from Câmara dos Deputados Open Data API
        self.camara_api = GovAPIClient("https://dadosabertos.camara.leg.br/api/v2")
        self.backend = BackendClient()

    def fetch_and_ingest_deputies(self, page: int = 1, fetch_items: int = 50):
        """Fetches active deputies and sends them to the Core API."""
        logger.info(f"Fetching deputies from Camara API (page {page})...")
        params = {"pagina": page, "itens": fetch_items}
        
        response = self.camara_api.get("deputados", params=params)
        if not response or "dados" not in response:
            logger.error("Failed to parse response or no data returned.")
            return

        deputies = response["dados"]
        for d in deputies:
            politician_payload = {
                "externalId": f"camara_{d['id']}",
                "name": d["nome"],
                "party": d["siglaPartido"],
                "state": d["siglaUf"],
                "position": "Deputado Federal"
            }
            logger.info(f"Ingesting: {politician_payload['name']} ({politician_payload['party']}-{politician_payload['state']})")
            self.backend.ingest_politician(politician_payload)
            
if __name__ == "__main__":
    gatherer = CamaraGatherer()
    # Fetch just the first page (50 deputies) for testing purposes
    gatherer.fetch_and_ingest_deputies(page=1, fetch_items=50)

