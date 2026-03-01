import requests
import re
from typing import List, Dict
import logging
from src.core.storage_util import save_downloaded_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CamaraNLPGatherer:
    """
    Crawler NLP para detectar 'Zero-Atividade' de um funcionário do gabinete.
    Busca o nome do assessor nas transcrições de discursos e ementas de projetos
    da Câmara dos Deputados, salvando localmente o conteúdo auditado.
    """
    def __init__(self):
        self.base_url = "https://dadosabertos.camara.leg.br/api/v2"

    def fetch_discursos(self, deputado_id: int, start_date: str, end_date: str) -> List[Dict]:
        url = f"{self.base_url}/deputados/{deputado_id}/discursos"
        params = {"dataInicio": start_date, "dataFim": end_date, "ordem": "ASC", "ordenarPor": "dataHoraInicio"}
        
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json().get("dados", [])
        except requests.RequestException as e:
            logger.warning(f"Falha ao buscar discursos do deputado {deputado_id}: {e}")
            return []

    def analyze_zero_activity(self, deputado_id: int, assessor_name: str, start_date: str, end_date: str) -> Dict:
        """
        Calcula o Zero-Activity cruzando o nome do assessor em transcrições
        de discursos do deputado.
        """
        logger.info(f"Analisando discursos do Deputado {deputado_id} buscando pelo assessor '{assessor_name}'")
        discursos = self.fetch_discursos(deputado_id, start_date, end_date)
        mentions = 0
        saved_files = []
        
        for d in discursos:
            text = d.get("transcricao", "")
            if not text:
                continue
            
            # Save downloaded text for audit
            data_hora = d.get('dataHoraInicio', '').replace(":", "-")
            filename = f"discurso_{deputado_id}_{data_hora}.txt"
            
            try:
                save_downloaded_file("camara_docs", filename, text)
                saved_files.append(filename)
            except Exception as e:
                logger.error(f"Erro ao salvar arquivo de auditoria {filename}: {e}")
            
            # Simple Regex NLP: match exact name ignoring case
            if re.search(r'\b' + re.escape(assessor_name) + r'\b', text, re.IGNORECASE):
                mentions += 1
                
        return {
            "assessor_name": assessor_name,
            "total_discursos_analyzed": len(discursos),
            "mentions_found": mentions,
            "is_zero_activity": mentions == 0,
            "files_saved": saved_files
        }

    def run(self, limit: int = 20):
        """
        Iterates over politicians and downloads their documents for future audit.
        """
        logger.info(f"Starting CamaraNLPGatherer batch document download (limit={limit})...")
        from src.core.api_client import GovAPIClient
        gov = GovAPIClient(self.base_url)
        
        # Fetch deputies
        resp = gov.get("deputados", params={"pagina": 1, "itens": limit})
        if not resp or "dados" not in resp:
            logger.error("Failed to fetch deputies for NLP download.")
            return

        for dep in resp["dados"]:
            dep_id = dep["id"]
            dep_name = dep["nome"]
            logger.info(f"Downloading documents for {dep_name} (ID: {dep_id})...")
            # Fetch last year's speeches
            discursos = self.fetch_discursos(dep_id, "2024-01-01", "2025-12-31")
            count = 0
            for d in discursos:
                text = d.get("transcricao", "")
                if text:
                    data_hora = d.get('dataHoraInicio', '').replace(":", "-").replace("T", "_")
                    filename = f"discurso_{dep_id}_{data_hora}.txt"
                    save_downloaded_file("camara_docs", filename, text)
                    count += 1
            logger.info(f"  -> Saved {count} speeches for {dep_name}.")

if __name__ == "__main__":
    # Test
    gatherer = CamaraNLPGatherer()
    # Deputado Baleia Rossi (exemplo) id: 178949 (random, using random id just for testing)
    # Assessor Fantasma Fake
    res = gatherer.analyze_zero_activity(178949, "João da Silva", "2023-01-01", "2023-12-31")
    print(res)
