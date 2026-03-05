"""
Absences Worker - Counts real plenary absences from the Câmara dos Deputados API.

Strategy: 
1. Fetches all plenary sessions (Sessão Deliberativa) for the year.
2. For each deputy, fetches their event participation list.
3. Compares to calculate how many sessions they missed.

Optimization: 
Saves results per deputy in `data/absences/absences_<nome>_<id>.json`. 
O JSON possui uma chave "resumo" no topo com os dados vitais para relatórios LLM rápidos,
e uma chave "detalhes" com os arrays pesados para ingestão no Grafo.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging
import argparse

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from workers.src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
WORKER_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ABSENCES_DIR = WORKER_ROOT / "data" / "absences"

class AbsencesWorker:
    def __init__(self, year: int = 2025):
        self.api = GovAPIClient(CAMARA_API_BASE, request_delay=0.3)
        self.backend = BackendClient()
        self.year = year
        self.current_year = datetime.now().year
        ABSENCES_DIR.mkdir(parents=True, exist_ok=True)

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

    def _count_plenary_events(self, deputy_id: int, external_id: str) -> list:
        """Fetch detailed sessions from the API and returns a list of sessions."""
        sessions_found = []
        page = 1
        
        # Trava a pesquisa no dia de hoje para o ano atual
        data_fim = datetime.now().strftime("%Y-%m-%d") if self.year == self.current_year else f"{self.year}-12-31"

        while True:
            resp = self.api.get(
                f"deputados/{deputy_id}/eventos",
                params={
                    "dataInicio": f"{self.year}-01-01",
                    "dataFim": data_fim,
                    "pagina": page,
                    "itens": 100
                }
            )
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            for evt in resp["dados"]:
                desc_tipo = evt.get("descricaoTipo", "")
                if "Deliberativa" in desc_tipo:
                    data_hora = evt.get("dataHoraInicio", "")
                    data_str = data_hora.split("T")[0] if "T" in data_hora else data_hora
                    sessions_found.append({
                        "id": f"sessao_{evt.get('id', '')}",
                        "data": data_str,
                        "tipo": "Sessao Deliberativa",
                        "local": "DF"
                    })
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
            if page > 5:  # Safety break
                break
        return sessions_found

    def _estimate_total_sessions(self) -> int:
        """Estimates total plenary sessions in the year by checking the main events endpoint."""
        total = 0
        page = 1
        
        # Trava a data no dia de hoje se for o ano atual para a API não falhar
        data_fim = datetime.now().strftime("%Y-%m-%d") if self.year == self.current_year else f"{self.year}-12-31"

        while True:
            resp = self.api.get(
                "eventos",
                params={
                    "dataInicio": f"{self.year}-01-01",
                    "dataFim": data_fim,
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

    def _get_cache_filepath(self, name: str, dep_id: int) -> Path:
        """Generate safe filename for the local cache."""
        safe_name = name.replace(" ", "_").replace("/", "_").lower()
        return ABSENCES_DIR / f"absences_{safe_name}_{dep_id}.json"

    def _load_cache(self, filepath: Path) -> dict:
        """Load JSON cache if exists."""
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self, filepath: Path, data: dict):
        """Save JSON cache to disk."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _is_cache_valid(self, year_summary: dict) -> bool:
        """
        Check if the data for this year is fresh enough to use without API calls.
        Lê estritamente o bloco de resumo.
        """
        if not year_summary:
            return False
            
        last_update_str = year_summary.get("ultima_atualizacao")
        if not last_update_str:
            return False

        if self.year < self.current_year:
            return True  # Histórico não muda

        # Verifica se tem menos de 7 dias
        last_update = datetime.fromisoformat(last_update_str)
        if datetime.now() - last_update < timedelta(days=7):
            return True
            
        return False

    def run(self, limit: int = 50):
        """Main execution flow with Cache-First strategy and Summary Object."""
        logger.info(f"=== Absences Worker - Calculating {self.year} absences ===")

        logger.info("Step 1: Estimating total plenary sessions...")
        base_total_sessions = self._estimate_total_sessions()
        
        # Só aplicamos o chute de 100 sessões para os ANOS PASSADOS, caso a API caia. Nunca para o ano atual.
        if base_total_sessions == 0 and self.year < self.current_year:
            base_total_sessions = 100
            
        logger.info(f"  -> Estimated {base_total_sessions} plenary sessions globally in {self.year}")

        logger.info("Step 2: Fetching deputies...")
        deputies = self._fetch_all_deputies()
        logger.info(f"  -> Found {len(deputies)} deputies. Processing first {limit}...")

        for i, dep in enumerate(deputies[:limit]):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"
            
            cache_file = self._get_cache_filepath(name, dep_id)
            cache_data = self._load_cache(cache_file)
            str_year = str(self.year)
            
            # --- NOVA ESTRUTURA: LER APENAS O BLOCO RESUMO ---
            resumo = cache_data.get("resumo", {})
            year_summary = resumo.get(str_year, {})

            if self._is_cache_valid(year_summary):
                logger.info(f"[{i+1}/{limit}] {name} - 📂 Lendo do Cache Local (Atualizado em {year_summary['ultima_atualizacao']})")
                attended = year_summary.get("presencas_totais", 0)
                absences = year_summary.get("faltas_estimadas", 0)
                real_total = year_summary.get("sessoes_legislativas_totais", base_total_sessions)
                
                # Para carregar no Neo4j, pegamos os detalhes de forma separada
                detalhes = cache_data.get("detalhes", {})
                sessions = detalhes.get(str_year, {}).get("sessoes", [])
                
                for sessao in sessions:
                    self.backend.ingest_sessao(external_id, sessao)
            else:
                logger.info(f"[{i+1}/{limit}] {name} - 🌐 Consultando API Câmara...")
                sessions = self._count_plenary_events(dep_id, external_id)
                attended = len(sessions)
                
                # Se a API geral encontrou 0 sessões, mas ele participou em 10, o total passa a ser no mínimo 10!
                real_total = max(base_total_sessions, attended)
                absences = max(0, real_total - attended)
                
                # --- ATUALIZA E SALVA A NOVA ESTRUTURA DO JSON ---
                if "resumo" not in cache_data:
                    cache_data["resumo"] = {}
                if "detalhes" not in cache_data:
                    cache_data["detalhes"] = {}
                    
                cache_data["resumo"][str_year] = {
                    "ano": self.year,
                    "ultima_atualizacao": datetime.now().isoformat(),
                    "sessoes_legislativas_totais": real_total,
                    "presencas_totais": attended,
                    "faltas_estimadas": absences
                }
                
                cache_data["detalhes"][str_year] = {
                    "sessoes": sessions
                }
                self._save_cache(cache_file, cache_data)

            logger.info(f"  -> Attended {attended}/{real_total} = {absences} absences")

            # Atualiza o Político no BD Analítico
            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "absences": absences,
                "presences": attended
            })

        logger.info("=== Absences Worker Complete ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker de Absenças com Data Lake Cache")
    parser.add_argument("--limit", type=int, default=15, help="Number of parliamentarians to process")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Year to process")
    args = parser.parse_args()
    
    worker = AbsencesWorker(year=args.year)
    worker.run(limit=args.limit)