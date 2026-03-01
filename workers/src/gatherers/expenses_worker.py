"""
Expenses Worker - Extracts real expense data from the Câmara dos Deputados API.

Strategy: For each politician, fetches ALL expense records for a given year,
sums up the total, and pushes a single aggregated value to the backend.
This optimizes storage by only persisting the total instead of every receipt.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
from src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

class ExpensesWorker:
    def __init__(self, year: int = 2025):
        self.api = GovAPIClient(CAMARA_API_BASE, request_delay=0.3)
        self.backend = BackendClient()
        self.year = year

    def _fetch_all_deputies(self) -> list:
        """Fetch all active deputy IDs and external IDs."""
        all_deputies = []
        page = 1
        while True:
            resp = self.api.get("deputados", params={"pagina": page, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"})
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            all_deputies.extend(resp["dados"])
            # Check if there's a next page
            links = resp.get("links", [])
            has_next = any(l.get("rel") == "next" for l in links)
            if not has_next:
                break
            page += 1
        return all_deputies

    def _aggregate_expenses(self, deputy_id: int, external_id: str) -> float:
        """Fetches all expense pages for a deputy in the given year and sums totals.
        Optimized: only stores the aggregated sum, not individual receipts.
        NEW: Also posts individual receipts for specific categories (spatial anomaly)."""
        valid_categories = ["FORNECIMENTO DE ALIMENTAÇÃO", "HOSPEDAGEM", "LOCAÇÃO OU FRETAMENTO DE VEÍCULOS AUTOMOTORES"]
        total = 0.0
        page = 1
        while True:
            resp = self.api.get(
                f"deputados/{deputy_id}/despesas",
                params={"ano": self.year, "pagina": page, "itens": 100, "ordem": "ASC"}
            )
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            for d in resp["dados"]:
                valor = d.get("valorLiquido", 0.0)
                total += valor
                
                categoria = d.get("tipoDespesa", "").upper()
                if categoria in valid_categories:
                    # Parse date safely (camara API format varies, usually has dataDocumento)
                    data_doc = d.get("dataDocumento", "")
                    # fallback to string if none
                    data_str = str(data_doc).split("T")[0] if isinstance(data_doc, str) and "T" in data_doc else str(data_doc) if data_doc else None
                    
                    if data_str:
                        despesa_node = {
                            "id": f"despesa_{d.get('codDocumento', d.get('numDocumento', 'unknown'))}",
                            "dataEmissao": data_str[:10],
                            "ufFornecedor": d.get("siglaUF", "NA"),
                            "categoria": categoria,
                            "valorDocumento": valor,
                            "nomeFornecedor": d.get("nomeFornecedor", "Unknown")
                        }
                        self.backend.ingest_despesa(external_id, despesa_node)
            links = resp.get("links", [])
            has_next = any(l.get("rel") == "next" for l in links)
            if not has_next:
                break
            page += 1
        return round(total, 2)

    def run(self, limit: int = 50):
        """Main execution: fetch deputies, aggregate expenses, push to backend."""
        logger.info(f"=== Expenses Worker - Extracting {self.year} expenses ===")
        deputies = self._fetch_all_deputies()
        logger.info(f"Found {len(deputies)} deputies. Processing first {limit}...")

        for i, dep in enumerate(deputies[:limit]):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"

            logger.info(f"[{i+1}/{limit}] {name} - Fetching {self.year} expenses...")
            total_expenses = self._aggregate_expenses(dep_id, external_id)
            logger.info(f"  -> Total: R$ {total_expenses:,.2f}")

            # Update only the expenses field for this politician
            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "expenses": total_expenses
            })

        logger.info("=== Expenses Worker Complete ===")


if __name__ == "__main__":
    worker = ExpensesWorker(year=2025)
    worker.run(limit=50)
