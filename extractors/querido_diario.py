# extractors/querido_diario.py
import httpx
import polars as pl
from pathlib import Path
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE = "https://queridodiario.ok.org.br/api"
RAW_DIR = Path("data/raw/diarios")
RAW_DIR.mkdir(parents=True, exist_ok=True)

async def extrair_dispensas_licitacao(territory_ids: list[str], desde: str):
    """Busca 'Dispensa de Licitação' e 'Inexigibilidade' nos diários municipais."""
    termos = ["dispensa de licitação", "inexigibilidade"]
    resultados = []

    logger.info(f"Buscando atos oficiais desde {desde} para {len(territory_ids)} territórios...")
    async with httpx.AsyncClient(timeout=30) as client:
        for tid in territory_ids:
            for termo in termos:
                offset = 0
                while True:
                    r = await client.get(
                        f"{BASE}/gazettes",
                        params={
                            "territory_id": tid,
                            "querystring": termo,
                            "since": desde,
                            "offset": offset,
                            "size": 100
                        }
                    )
                    if r.status_code != 200: 
                        logger.error(f"Erro na API Querido Diário: {r.status_code}")
                        break
                    
                    try:
                        data = r.json()
                    except Exception as e:
                        logger.error(f"Erro ao parsear JSON Querido Diário: {e}")
                        break
                    gazettes = data.get("gazettes", [])
                    if not gazettes:
                        break
                    for g in gazettes:
                        for excerto in g.get("excerts", []):
                            resultados.append({
                                "territory_id": tid,
                                "territory_name": g.get("territory_name", ""),
                                "date": g["date"],
                                "tipo_busca": termo,
                                "excerto": excerto,
                                "url_diario": g.get("url", ""),
                            })
                    offset += 100
                    if offset > 200: break # Dev limit

    if resultados:
        df = pl.DataFrame(resultados)
        output_path = RAW_DIR / f"dispensas_{desde}_raw.parquet"
        df.write_parquet(output_path)
        logger.info(f"Encontrados {len(resultados)} excertos em {output_path}")
        return df
    return None

if __name__ == "__main__":
    # Test with São Paulo (3550308)
    asyncio.run(extrair_dispensas_licitacao(["3550308"], "2025-01-01"))
