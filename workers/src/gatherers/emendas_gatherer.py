import os
import logging
import random
from datetime import datetime
from typing import Dict, Any, List
from src.core.api_client import BackendClient, PortalTransparenciaClient, GovAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmendasGatherer:
    def __init__(self, target_politicians: List[Dict[str, Any]], limit: int = 10):
        self.politicians = target_politicians[:limit]
        self.backend = BackendClient()
        self.api_key = os.getenv("PORTAL_API_KEY", "")
        self.portal = PortalTransparenciaClient(api_key=self.api_key)
        self.camara = GovAPIClient("https://dadosabertos.camara.leg.br/api/v2")

    async def _fetch_real_emendas(self, politician: Dict[str, Any]):
        pol_id = politician.get("externalId", "").replace("camara_", "")
        if not pol_id:
            return

        dep_detail = self.camara.get(f"deputados/{pol_id}")
        if not dep_detail or "dados" not in dep_detail:
            logger.warning(f"Could not fetch details for deputy {pol_id}")
            return
            
        cpf = dep_detail["dados"].get("cpf")
        name = dep_detail["dados"].get("nomeCivil")

        logger.info(f"🔍 Extraindo TODAS as emendas de {name} (CPF: {cpf[:3]}...) de 2022 até hoje...")
        
        if not self.api_key:
            logger.warning(f"  ⚠️ Pulando Emendas de {name} (Falta a PORTAL_API_KEY)")
            return
            
        current_year = datetime.now().year
        total_emendas_salvas = 0
        
        # 1. Loop através dos Anos (2022 até Atual)
        for ano in range(2022, current_year + 1):
            page = 1
            
            # 2. Paginação (Vai virando a página até acabar as emendas daquele ano)
            while True:
                params = {"codigoAutor": cpf, "ano": ano, "pagina": page}
                emendas = self.portal.get("emendas", params=params)
                
                if not emendas:
                    params = {"nomeAutor": name, "ano": ano, "pagina": page}
                    emendas = self.portal.get("emendas", params=params)

                if not emendas:
                    break
                    
                for em in emendas:
                    codigo = em.get("codigoEmenda", f"EM_{random.randint(1000, 9999)}")
                    
                    raw_valor = em.get("valorPago", em.get("valorEmpenhado", 0))
                    if isinstance(raw_valor, str):
                        raw_valor = raw_valor.replace(".", "").replace(",", ".")
                    
                    try:
                        valor = float(raw_valor)
                    except (ValueError, TypeError):
                        valor = 0.0
                    
                    tipo_emenda = em.get("tipoEmenda", "Transferência Especial")
                    
                    funcao = em.get("funcao", em.get("nomeFuncao", ""))
                    if not funcao or str(funcao).strip() == "":
                        funcao = "Não Especificada"
                        
                    subfuncao = em.get("subfuncao", "")
                    if subfuncao and funcao != "Não Especificada":
                        funcao = f"{funcao} ({subfuncao})"
                        
                    localidade = em.get("localidadeDoGasto", "")
                    
                    municipios_array = em.get("municipios", [])
                    municipio_ibge = None
                    
                    if municipios_array and isinstance(municipios_array, list) and len(municipios_array) > 0:
                        mun = municipios_array[0]
                        codigo_ibge_raw = mun.get("codigoIBGE", "")
                        if codigo_ibge_raw:
                            municipio_ibge = str(codigo_ibge_raw)
                            
                        if not localidade or str(localidade).strip() == "":
                            nome_cidade = mun.get("nomeIBGE", mun.get("nomeMunicipio", ""))
                            if nome_cidade:
                                localidade = f"{nome_cidade}"

                    if not municipio_ibge:
                        uf = em.get("ufBeneficiario", "")
                        if uf:
                            municipio_ibge = f"ESTADO_{uf}"
                            # Preenche a localidade com o Estado se estiver vazia
                            if not localidade or str(localidade).strip() == "":
                                localidade = f"Governo Estadual ({uf})"
                        else:
                            # Dinheiro de nível Nacional
                            if not localidade or str(localidade).strip() == "":
                                localidade = "Nacional / Múltiplo"
                                
                    emenda_node = {
                        "id": codigo,
                        "ano": ano,
                        "valor": valor,
                        "tipo": tipo_emenda,
                        "funcao": funcao,           # Ex: Saúde (Atenção Básica)
                        "localidade": localidade    # Ex: Macapá ou Governo Estadual (AP)
                    }
                            
                    logger.info(f"  -> Emenda [{ano}]: {codigo} (R$ {valor:,.2f}) -> {localidade} | {funcao}")
                    self.backend.ingest_emenda_pix(politician.get("externalId"), municipio_ibge, emenda_node)
                    total_emendas_salvas += 1
                
                page += 1
                if page > 50:
                    break

        logger.info(f"  ✅ TOTAL: {total_emendas_salvas} emendas rastreadas e salvas para {name}.")

    def run(self):
        logger.info(f"Iniciando EmendasGatherer para {len(self.politicians)} políticos.")
        import asyncio
        loop = asyncio.get_event_loop()
        
        count = 0
        for p in self.politicians:
            loop.run_until_complete(self._fetch_real_emendas(p))
            count += 1
        logger.info(f"EmendasGatherer finalizado com sucesso para {count} políticos.")