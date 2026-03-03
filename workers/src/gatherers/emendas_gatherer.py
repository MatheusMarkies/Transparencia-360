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
            # Puxa o ano e código
            ano = em.get("ano", 2025)
            codigo = em.get("codigoEmenda", f"EM_{random.randint(1000, 9999)}")
            
            # 1. Pega o Valor Pago (ou Empenhado se ainda não pagou)
            raw_valor = em.get("valorPago", em.get("valorEmpenhado", 0))
            
            # 2. Formata de "1.500.000,00" para "1500000.00" antes do float()
            if isinstance(raw_valor, str):
                raw_valor = raw_valor.replace(".", "").replace(",", ".")
            
            try:
                valor = float(raw_valor)
            except (ValueError, TypeError):
                valor = 0.0
            
            # Beneficiaries: Usually emendas have a list of local transfers
            tipo_emenda = em.get("tipoEmenda", "Transferência Especial")
            
            emenda_node = {
                "id": codigo,
                "ano": ano,
                "valor": valor,
                "tipo": tipo_emenda
            }
            
            # Busca município no detalhe (o campo geralmente é 'localidade do gasto')
            municipio_nome = em.get("localidade do gasto", "")
            municipio_ibge = "3304557" # Fallback temporário
            
            logger.info(f"  -> Ingesting real Emenda: {codigo} (R$ {valor:,.2f}) - {tipo_emenda}")
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
