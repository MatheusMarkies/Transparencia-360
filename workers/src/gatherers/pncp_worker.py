"""
PNCP Worker - Extracts municipal bidding data from the Portal Nacional de Contratações Públicas.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import httpx
import asyncio
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PNCPWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.base_url = "https://pncp.gov.br/api/consulta/v1"

    async def extract_contracts(self, cnpj: str = "00000000000191", page: int = 1):
        """Extracts contracts for a specific CNPJ (defaulting to a generic one or a known municipality)."""
        logger.info(f"Extracting PNCP contracts for CNPJ {cnpj}, page {page}...")
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                # The endpoint for contracts by organization
                url = f"{self.base_url}/contratacoes"
                params = {
                    "pagina": page,
                    "tamanhoPagina": 10,
                    "cnpjOrgao": cnpj
                }
                
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    logger.warning(f"PNCP: No data found for CNPJ {cnpj} at {url}")
                    return []
                
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", [])
                
                logger.info(f"  Found {len(items)} items in PNCP")
                
                for item in items:
                    # Map PNCP fields to Backend Ingest format
                    # PNCP has a rich schema; we'll pick the essentials for 'ScannerDiarios'
                    payload = {
                        "externalId": f"pncp_{item.get('id')}",
                        "source": "PNCP",
                        "title": item.get("objetoContratacao", "Compra sem título"),
                        "description": f"Tipo: {item.get('modalidadeNome')} | Valor: {item.get('valorTotalEstimado')}",
                        "municipalityId": item.get("orgaoEntidade", {}).get("cnpj"),
                        "date": item.get("dataPublicacaoPncp"),
                        "riskScore": 0, # To be calculated by analyzer
                    }
                    # self.backend.ingest_document(payload) # Assuming ingest_document exists or similar
                    logger.info(f"  Ingested PNCP item: {payload['externalId']}")
                
                return items
            except Exception as e:
                logger.error(f"Error in PNCPWorker: {e}")
                return []

    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.extract_contracts())

if __name__ == "__main__":
    worker = PNCPWorker()
    worker.run()
