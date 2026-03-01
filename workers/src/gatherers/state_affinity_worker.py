"""
State Affinity Worker - Calculates how much a politician's expenses focus on their home state.

Strategy:
1. Fetches all expense records for a deputy.
2. Checks each expense's supplier location (CNPJ prefix or state indicator from data).
3. Since the API doesn't directly expose supplier state, we use a heuristic:
   We look at expense type distribution - "PASSAGENS AÉREAS" suggests travel away from state,
   while "ESCRITÓRIO" and "LOCAÇÃO" expenses suggest in-state activity.
4. Computes a ratio of in-state vs. out-of-state focused expenses.

Optimization: Only stores a single float (0.0-1.0) per politician.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
from src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

# Expense types that suggest in-state activity
IN_STATE_TYPES = [
    "MANUTENÇÃO DE ESCRITÓRIO",
    "LOCAÇÃO OU FRETAMENTO",
    "SERVIÇO DE SEGURANÇA",
    "ASSINATURA",
    "COMBUSTÍVEIS",
    "TELEFONIA",
    "HOSPEDAGEM",
    "ALIMENTAÇÃO",
    "SERVIÇOS POSTAIS",
    "CONSULTORIAS",
]

# Expense types that suggest out-of-state / Brasília activity
OUT_STATE_TYPES = [
    "PASSAGENS AÉREAS",
    "PASSAGEM AÉREA",
    "EMISSÃO BILHETE AÉREO",
]


class StateAffinityWorker:
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

    def _calculate_affinity(self, deputy_id: int) -> float:
        """Analyzes expense types to estimate how much activity is focused on home state.
        Returns a value between 0.0 and 1.0."""
        in_state_value = 0.0
        out_state_value = 0.0
        total_value = 0.0
        page = 1

        while True:
            resp = self.api.get(
                f"deputados/{deputy_id}/despesas",
                params={"ano": self.year, "pagina": page, "itens": 100}
            )
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break

            for d in resp["dados"]:
                tipo = d.get("tipoDespesa", "").upper()
                valor = d.get("valorLiquido", 0.0)
                total_value += valor

                # Check if it's an out-of-state type (air travel)
                is_out = any(out_type in tipo for out_type in OUT_STATE_TYPES)
                if is_out:
                    out_state_value += valor
                else:
                    in_state_value += valor

            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
            # Limit pages for speed
            if page > 5:
                break

        if total_value == 0:
            return 0.5  # default when no data

        # Affinity = percentage of expenses NOT spent on air travel (out-of-state)
        affinity = in_state_value / total_value
        return round(min(max(affinity, 0.0), 1.0), 2)

    def run(self, limit: int = 50):
        logger.info(f"=== State Affinity Worker - Analyzing {self.year} expense patterns ===")
        deputies = self._fetch_all_deputies()
        logger.info(f"Found {len(deputies)} deputies. Processing first {limit}...")

        for i, dep in enumerate(deputies[:limit]):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"

            logger.info(f"[{i+1}/{limit}] {name} - Analyzing expense patterns...")
            affinity = self._calculate_affinity(dep_id)
            logger.info(f"  -> State Affinity: {affinity:.0%}")

            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "stateAffinity": affinity
            })

        logger.info("=== State Affinity Worker Complete ===")


if __name__ == "__main__":
    worker = StateAffinityWorker(year=2025)
    worker.run(limit=50)
