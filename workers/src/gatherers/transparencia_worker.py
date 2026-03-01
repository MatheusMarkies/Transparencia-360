"""
Portal da Transparência Worker - Extracts federal transparency data.

The Portal da Transparência API (api.portaldatransparencia.gov.br) requires an API key.
This worker uses a no-auth approach by accessing public CSV/JSON datasets:
- Viagens a serviço (official travels)
- Cartões de pagamento (gov credit card usage)

For a production deployment, register for a free API key at:
https://portaldatransparencia.gov.br/api-de-dados/

In this prototype, we query the Câmara API's proposition endpoints 
to enrich politicians with their authored legislation count, as a 
proxy for legislative productivity — available without auth.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
from src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

class TransparenciaWorker:
    """Enriches politician data using publicly available transparency endpoints.
    
    Uses the Câmara API to fetch:
    1. Number of authored propositions (legislative productivity)
    2. Number of frentes parlamentares (caucuses joined)
    
    These act as transparency indicators showing how active a politician is.
    """
    def __init__(self, year: int = 2025):
        self.api = GovAPIClient(CAMARA_API_BASE, request_delay=0.3)
        self.backend = BackendClient()
        self.year = year

    def _fetch_all_deputies(self) -> list:
        all_deps = []
        page = 1
        while True:
            resp = self.api.get("deputados", params={"pagina": page, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"})
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            all_deps.extend(resp["dados"])
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
        return all_deps

    def _count_authored_propositions(self, deputy_id: int) -> int:
        """Counts propositions authored by this deputy in the current legislature.
        Optimized: only stores the count, not each proposition."""
        resp = self.api.get(
            "proposicoes",
            params={
                "idDeputadoAutor": deputy_id,
                "ano": self.year,
                "itens": 1,
                "pagina": 1
            }
        )
        if not resp or "dados" not in resp:
            return 0
        # Use pagination info to get total count without fetching all pages
        links = resp.get("links", [])
        last_link = next((l for l in links if l.get("rel") == "last"), None)
        if last_link and "pagina=" in last_link.get("href", ""):
            # Extract total from last page number
            href = last_link["href"]
            try:
                import re
                match = re.search(r'pagina=(\d+)', href)
                if match:
                    return int(match.group(1))
            except Exception:
                pass
        return len(resp.get("dados", []))

    def _count_frentes(self, deputy_id: int) -> int:
        """Counts frentes parlamentares (caucuses) the deputy participates in."""
        resp = self.api.get(f"deputados/{deputy_id}/frentes")
        if not resp or "dados" not in resp:
            return 0
        return len(resp["dados"])

    def run(self, limit: int = 50):
        logger.info(f"=== Transparência Worker - Legislative Productivity {self.year} ===")
        deputies = self._fetch_all_deputies()
        logger.info(f"Found {len(deputies)} deputies. Processing first {limit}...")

        for i, dep in enumerate(deputies[:limit]):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"

            logger.info(f"[{i+1}/{limit}] {name} - Counting propositions & caucuses...")
            propositions = self._count_authored_propositions(dep_id)
            frentes = self._count_frentes(dep_id)
            logger.info(f"  -> {propositions} propositions, {frentes} caucuses")

            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "propositions": propositions,
                "frentes": frentes
            })

        logger.info("=== Transparência Worker Complete ===")


if __name__ == "__main__":
    worker = TransparenciaWorker(year=2025)
    worker.run(limit=50)
