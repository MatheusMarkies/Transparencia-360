import os
import logging
import random
from typing import Dict, Any, List
from src.core.api_client import BackendClient, PortalTransparenciaClient, GovAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Real-world data extraction logic for Emendas and Municipal Contracts.

class EmendasGatherer:
    def __init__(self, target_politicians: List[Dict[str, Any]], limit: int = 10):
        self.politicians = target_politicians[:limit]
        self.backend = BackendClient()
        self.api_key = os.getenv("PORTAL_API_KEY", "")
        self.portal = PortalTransparenciaClient(api_key=self.api_key)
        self.camara = GovAPIClient("https://dadosabertos.camara.leg.br/api/v2")

    async def _fetch_real_emendas(self, politician: Dict[str, Any]):
        """
        Fetches real Emendas from Portal da Transparência.
        Uses the name and CPF of the politician.
        """
        pol_id = politician.get("externalId", "").replace("camara_", "")
        if not pol_id:
            return

        # Fetch full deputy detail to get CPF
        dep_detail = self.camara.get(f"deputados/{pol_id}")
        if not dep_detail or "dados" not in dep_detail:
            logger.warning(f"Could not fetch details for deputy {pol_id}")
            return
            
        cpf = dep_detail["dados"].get("cpf")
        name = dep_detail["dados"].get("nomeCivil")

        logger.info(f"Fetching real emendas for {name} (CPF: {cpf[:3]}...)")
        
        # Endpoint: /emendas
        # Documentation: https://api.portaldatransparencia.gov.br/swagger-ui.html#/Emendas/emendasUsandoGET
        # We can filter by 'cpfAutor' (if it works for deputies) or 'nomeAutor'
        if not self.api_key:
            logger.warning(f"  ⚠️ Skipping Emendas fetch for {name} (Missing PORTAL_API_KEY)")
            return
            
        params = {"nomeAutor": name, "pagina": 1}
        emendas = self.portal.get("emendas", params=params) or []
        
        if not emendas:
            # Try by CPF if name failed
            params = {"codigoAutor": cpf, "pagina": 1} # Author code is often the CPF
            emendas = self.portal.get("emendas", params=params) or []

        for em in emendas:
            # Ingest Emenda node
            # Format depends on Portal API response: {codigoEmenda, ano, valorEmenda, ...}
            ano = em.get("ano", 2024)
            codigo = em.get("codigoEmenda", f"EM_{random.randint(1000, 9999)}")
            valor = float(em.get("valorEmenda", 0))
            
            # Beneficiaries: Usually emendas have a list of local transfers
            # Reusing the emenda_node structure
            emenda_node = {
                "id": codigo,
                "ano": ano,
                "valor": valor,
                "tipo": em.get("tipoEmenda", "Transferência Especial")
            }
            
            # In a real deep dive, we'd find the municipality IBGE associated
            # For now, we search for the 'localidade' or 'beneficiario' in the emenda detail
            # Mocking the IBGE link for now until we have a municipality mapper
            municipio_ibge = "3304557" # Default to Rio for demo if IBGE not found
            
            logger.info(f"  -> Ingesting real Emenda: {codigo} (R$ {valor:,.2f})")
            self.backend.ingest_emenda_pix(politician.get("externalId"), municipio_ibge, emenda_node)

    def run(self):
        logger.info(f"Starting REAL EmendasGatherer for {len(self.politicians)} politicians.")
        import asyncio
        loop = asyncio.get_event_loop()
        
        count = 0
        for p in self.politicians:
            loop.run_until_complete(self._fetch_real_emendas(p))
            count += 1
            if count % 10 == 0:
                logger.info(f"Processed Emendas for {count}/{len(self.politicians)} politicians.")
        logger.info(f"EmendasGatherer finished successfully for {count} politicians.")
