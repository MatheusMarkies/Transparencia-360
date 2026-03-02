# extractors/camara_deputados.py
import httpx
import polars as pl
from pathlib import Path
import asyncio
import argparse
import logging
from datetime import datetime, timedelta, date

HOJE = date.today().strftime("%Y-%m-%d")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE = "https://dadosabertos.camara.leg.br/api/v2"

CURRENT_DIR = Path(__file__).resolve().parent
WORKER_ROOT = CURRENT_DIR.parent
RAW_DIR = WORKER_ROOT / "data" / "raw" / "camara"
RAW_DIR.mkdir(parents=True, exist_ok=True)


async def _buscar_deputados(client: httpx.AsyncClient, limit: int) -> list:
    """Busca a lista de deputados respeitando o limite global."""
    resp = await client.get(f"{BASE}/deputados", params={"itens": limit, "ordem": "ASC"})
    if resp.status_code != 200:
        logger.error(f"Erro na API de Deputados: {resp.status_code}")
        return []
    try:
        return resp.json()["dados"]
    except Exception as e:
        logger.error(f"Erro ao parsear deputados: {e}")
        return []


async def extrair_despesas_ceap(limit: int = 100, ano: int = 2025):
    """Extrai todas as despesas CEAP dos deputados (respeitando --limit)."""
    logger.info(f"Iniciando extração de despesas CEAP para o ano {ano} (Limite: {limit} deputados)...")
    async with httpx.AsyncClient(timeout=30) as client:
        deputados = await _buscar_deputados(client, limit)
        if not deputados:
            return None

        todas_despesas = []
        for dep in deputados:
            logger.info(f"Processando despesas de {dep['nome']}...")
            pagina = 1
            while True:
                params = {
                    "ano": ano,
                    "pagina": pagina,
                    "itens": 100
                }
                response = await client.get(f"{BASE}/deputados/{dep['id']}/despesas", params=params)

                if response.status_code != 200:
                    logger.warning(f"Erro ao buscar despesas para {dep['nome']}: {response.status_code}")
                    break

                try:
                    res_json = response.json()
                    dados = res_json.get("dados", [])
                except Exception as e:
                    logger.warning(f"Erro ao parsear despesas para {dep['nome']}: {e}")
                    break

                if not dados:
                    break
                for d in dados:
                    d["deputado_id"] = dep["id"]
                    d["deputado_nome"] = dep["nome"]
                    d["deputado_siglaPartido"] = dep.get("siglaPartido", "")
                    d["deputado_siglaUf"] = dep.get("siglaUf", "")
                todas_despesas.extend(dados)
                pagina += 1

        if todas_despesas:
            df = pl.DataFrame(todas_despesas)
            output_path = RAW_DIR / f"ceap_{ano}_raw.parquet"
            df.write_parquet(output_path)
            logger.info(f"Salvo {len(todas_despesas)} registros em {output_path}")
            return df
        return None


async def extrair_presencas(data_inicio: str, data_fim: str, limit: int = 100):
    """
    Extrai presenças no plenário — alimenta o Módulo 4 (Teletransporte).
    O parâmetro `limit` filtra para considerar apenas os mesmos N deputados
    usados no restante do pipeline, garantindo consistência.
    """
    logger.info(f"Extraindo presenças de {data_inicio} até {data_fim} (Limite: {limit} deputados)...")

    data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
    data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")
    presencas = []

    async with httpx.AsyncClient(timeout=30) as client:
        # Busca os mesmos deputados que o pipeline usa, para manter consistência
        deputados = await _buscar_deputados(client, limit)
        ids_validos = {dep["id"] for dep in deputados} if deputados else None

        data_atual = data_inicio_dt

        # Loop para contornar o limite de 30 dias da API
        while data_atual <= data_fim_dt:
            proxima_data = min(data_atual + timedelta(days=30), data_fim_dt)

            str_inicio = data_atual.strftime("%Y-%m-%d")
            str_fim = proxima_data.strftime("%Y-%m-%d")
            logger.info(f"  -> Consultando período: {str_inicio} a {str_fim}")

            resp = await client.get(
                f"{BASE}/eventos",
                params={
                    "dataInicio": str_inicio,
                    "dataFim": str_fim,
                    "itens": 100
                }
            )

            if resp.status_code != 200:
                logger.error(f"Erro na API de Eventos: {resp.status_code} - {resp.text}")
                data_atual = proxima_data + timedelta(days=1)
                continue

            try:
                eventos = resp.json().get("dados", [])
            except Exception:
                logger.error("Erro ao parsear eventos")
                eventos = []

            for evento in eventos:
                tipo_evento = evento.get("descricaoTipo", "")
                if "Sessão Deliberativa" not in tipo_evento:
                    continue

                r = await client.get(f"{BASE}/eventos/{evento['id']}/deputados")
                if r.status_code != 200:
                    continue

                try:
                    evento_dados = r.json().get("dados", [])
                except Exception:
                    continue

                for dep in evento_dados:
                    # Filtra apenas deputados dentro do limite do pipeline
                    if ids_validos is not None and dep["id"] not in ids_validos:
                        continue
                    presencas.append({
                        "evento_id": evento["id"],
                        "data": evento["dataHoraInicio"][:10],
                        "local": evento.get("localCamara", {}).get("nome", "Brasília"),
                        "deputado_id": dep["id"],
                        "deputado_nome": dep.get("nome", ""),
                    })

            data_atual = proxima_data + timedelta(days=1)

        if presencas:
            df = pl.DataFrame(presencas)
            output_path = RAW_DIR / f"presencas_{data_inicio}_{data_fim}.parquet"
            df.write_parquet(output_path)
            logger.info(f"Salvas {len(presencas)} presenças em {output_path}")
            return df

        logger.warning(f"Nenhuma presença encontrada entre {data_inicio} e {data_fim}.")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrator Câmara dos Deputados")
    parser.add_argument("--limit", type=int, default=100, help="Número de deputados a processar")
    args = parser.parse_args()

    LIMIT = args.limit
    logger.info(f"Executando com --limit={LIMIT}")

    asyncio.run(extrair_despesas_ceap(limit=LIMIT, ano=2024))
    asyncio.run(extrair_despesas_ceap(limit=LIMIT, ano=2025))
    asyncio.run(extrair_presencas("2025-01-01","2025-12-31",limit=LIMIT))
    asyncio.run(extrair_presencas("2026-01-01",HOJE,limit=LIMIT))