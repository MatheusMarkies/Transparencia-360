# extractors/portal_transparencia.py
import httpx
import polars as pl
from pathlib import Path
import os
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"
RAW_DIR = Path("data/raw/cgu")
RAW_DIR.mkdir(parents=True, exist_ok=True)

def get_headers():
    """Busca a chave dinamicamente para garantir que ela foi carregada."""
    api_key = os.getenv("PORTAL_API_KEY")
    if not api_key:
        logger.error("PORTAL_API_KEY não configurada no ambiente.")
        return None
    return {
        "chave-api-dados": api_key,
        "Accept": "application/json"  # Boa prática para garantir que a API retorne JSON
    }

async def extrair_emendas(ano: int = 2025):
    """Extrai emendas parlamentares — alimenta Módulo 5 (Emendas Pix)."""
    headers = get_headers()
    if not headers:
        return None

    logger.info(f"Extraindo emendas para o ano {ano}...")
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        pagina = 1
        registros = []
        while True:
            r = await client.get(
                f"{BASE}/emendas-parlamentares",
                params={"ano": ano, "pagina": pagina}
            )
            if r.status_code != 200: 
                logger.error(f"Erro na API de Emendas: {r.status_code} - {r.text}")
                break
            
            try:
                dados = r.json()
            except Exception as e:
                logger.error(f"Erro ao parsear JSON de emendas: {e}")
                break
            if not dados:
                break
            registros.extend(dados)
            pagina += 1
            if pagina > 10: break # Dev limit

        if registros:
            df = pl.DataFrame(registros)
            output_path = RAW_DIR / f"emendas_{ano}_raw.parquet"
            df.write_parquet(output_path)
            logger.info(f"Salvas {len(registros)} emendas em {output_path}")
            return df
        return None

async def extrair_servidores(orgao_siape: str = "01000"):
    """
    Extrai servidores federais — alimenta Módulo 1 (Rachadinha: assessores).
    Padrão: orgao_siape="01000" (Câmara dos Deputados).
    """
    headers = get_headers()
    if not headers:
        return None

    logger.info(f"Extraindo servidores federais do órgão SIAPE {orgao_siape}...")
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        pagina = 1
        registros = []
        while True:
            # OTIMIZAÇÃO: Filtro obrigatório 'orgaoServidorLotacao' adicionado
            r = await client.get(
                f"{BASE}/servidores", 
                params={
                    "pagina": pagina,
                    "orgaoServidorLotacao": orgao_siape
                }
            )
            if r.status_code != 200: 
                logger.error(f"Erro na API de Servidores: {r.status_code} - {r.text}")
                break
            
            try:
                dados = r.json()
            except Exception as e:
                logger.error(f"Erro ao parsear JSON de servidores: {e}")
                break
            if not dados:
                break
            registros.extend(dados)
            pagina += 1
            if pagina > 5: break # Dev limit

        if registros:
            df = pl.DataFrame(registros)
            output_path = RAW_DIR / "servidores_raw.parquet"
            df.write_parquet(output_path)
            logger.info(f"Salvos {len(registros)} servidores em {output_path}")
            return df
        return None

if __name__ == "__main__":
    asyncio.run(extrair_emendas())
    asyncio.run(extrair_servidores())