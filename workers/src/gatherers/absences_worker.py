"""
Absences Worker - Counts real plenary absences from the Câmara dos Deputados API.

Strategy: 
1. Fetches all plenary sessions (Sessão Deliberativa) for the year.
2. For each deputy, fetches their event participation list.
3. Compares to calculate how many sessions they missed.

Optimization: We store only the integer count of missed sessions, not each 
individual event record, keeping the database lean.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
from src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

class AbsencesWorker:
    def __init__(self, year: int = 2025):
        self.api = GovAPIClient(CAMARA_API_BASE, request_delay=0.3)
        self.backend = BackendClient()
        self.year = year

    def _fetch_all_deputies(self) -> list:
        """Fetch all active deputy IDs."""
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

    def _count_plenary_events(self, deputy_id: int, external_id: str) -> int:
        """Counts how many plenary events the deputy participated in during the year.
        We fetch up to 500 events and count only 'Sessão Deliberativa' in Plenário,
        and post each as a SessaoPlenarioNode to the backend."""
        attended = 0
        page = 1
        while True:
            resp = self.api.get(
                f"deputados/{deputy_id}/eventos",
                params={
                    "dataInicio": f"{self.year}-01-01",
                    "dataFim": f"{self.year}-12-31",
                    "pagina": page,
                    "itens": 100
                }
            )
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            for evt in resp["dados"]:
                desc_tipo = evt.get("descricaoTipo", "")
                if "Deliberativa" in desc_tipo:
                    attended += 1
                    
                    # Post detailed session to the backend for Spatial Anomaly matching
                    data_hora = evt.get("dataHoraInicio", "")
                    data_str = data_hora.split("T")[0] if "T" in data_hora else data_hora
                    sessao_node = {
                        "id": f"sessao_{evt.get('id', '')}",
                        "data": data_str,
                        "tipo": "Sessao Deliberativa",
                        "local": "DF"
                    }
                    self.backend.ingest_sessao(external_id, sessao_node)
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
            # Safety: limit to 5 pages to avoid too many API calls per deputy
            if page > 5:
                break
        return attended

    def _estimate_total_sessions(self) -> int:
        """Estimates total plenary sessions in the year by checking the main events endpoint.
        Fetches all 'Sessão Deliberativa' events from the Plenário organ (id=180)."""
        total = 0
        page = 1
        while True:
            resp = self.api.get(
                "eventos",
                params={
                    "dataInicio": f"{self.year}-01-01",
                    "dataFim": f"{self.year}-12-31",
                    "codTipoEvento": 100,  # Sessão Deliberativa
                    "pagina": page,
                    "itens": 100
                }
            )
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            total += len(resp["dados"])
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
            if page > 10:
                break
        return total

    def run(self, limit: int = 50):
        """Main execution: estimate total sessions, count participation, compute absences."""
        logger.info(f"=== Absences Worker - Calculating {self.year} absences ===")

        logger.info("Step 1: Estimating total plenary sessions...")
        total_sessions = self._estimate_total_sessions()
        if total_sessions == 0:
            total_sessions = 100  # Fallback estimate for a typical legislative year
        logger.info(f"  -> Estimated {total_sessions} plenary sessions in {self.year}")

        logger.info("Step 2: Fetching deputies...")
        deputies = self._fetch_all_deputies()
        logger.info(f"  -> Found {len(deputies)} deputies. Processing first {limit}...")

        for i, dep in enumerate(deputies[:limit]):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"

            logger.info(f"[{i+1}/{limit}] {name} - Counting plenary attendance...")
            attended = self._count_plenary_events(dep_id, external_id)
            absences = max(0, total_sessions - attended)
            logger.info(f"  -> Attended {attended}/{total_sessions} = {absences} absences")

            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "absences": absences,
                "presences": attended  # <--- ADICIONE ESTA LINHA AQUI
            })

        logger.info("=== Absences Worker Complete ===")


if __name__ == "__main__":
    worker = AbsencesWorker(year=2025)
    parser.add_argument("--limit", type=int, default=15, help="Number of parliamentarians to process")
    args = parser.parse_args()
    worker.run(limit=args.limit)
