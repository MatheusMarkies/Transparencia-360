import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
from src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SenadoGatherer:
    def __init__(self):
        # Base URL from Senado Federal Open Data API
        self.senado_api = GovAPIClient("https://legis.senado.leg.br/dadosabertos")
        self.backend = BackendClient()

    def fetch_and_ingest_senators(self):
        """Fetches active senators and sends them to the Core API."""
        logger.info(f"Fetching active senators from Senado API...")
        
        response = self.senado_api.get("senador/lista/atual.json")
        if not response or "ListaParlamentarEmExercicio" not in response:
            logger.error("Failed to parse response or no data returned.")
            return

        try:
            senators = response["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
        except KeyError as e:
            logger.error(f"Unexpected JSON structure from Senado API: {e}")
            return

        for s in senators:
            identidade = s.get("IdentificacaoParlamentar", {})
            politician_payload = {
                "externalId": f"senado_{identidade.get('CodigoParlamentar')}",
                "name": identidade.get("NomeParlamentar", "N/A"),
                "party": identidade.get("SiglaPartidoParlamentar", "N/A"),
                "state": identidade.get("UfParlamentar", "N/A"),
                "position": "Senador(a)"
            }
            logger.info(f"Ingesting: {politician_payload['name']} ({politician_payload['party']}-{politician_payload['state']})")
            self.backend.ingest_politician(politician_payload)
            
if __name__ == "__main__":
    gatherer = SenadoGatherer()
    gatherer.fetch_and_ingest_senators()
