import polars as pl
import httpx
import logging
import asyncio
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8080/api/internal/workers/ingest"

async def process_row(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, row: dict, politicians_processed: set):
    """Processa uma única linha de despesa de forma assíncrona."""
    async with semaphore:
        external_id = f"camara_{row['deputado_id']}"
        
        try:
            # OTIMIZAÇÃO: Verifica se o político já foi processado nesta execução
            if external_id not in politicians_processed:
                politician_data = {
                    "externalId": external_id,
                    "name": row["deputado_nome"],
                    "party": row["deputado_siglaPartido"],
                    "state": row["deputado_siglaUf"],
                    "position": "Deputado Federal"
                }
                
                # Envia o político e adiciona ao cache para não enviar de novo
                await client.post(f"{BACKEND_URL}/politician", json=politician_data)
                politicians_processed.add(external_id)
            
            # Preparação dos dados da despesa
            provider_name = str(row.get("txtFornecedor", row.get("nomeFornecedor", "UNKNOWN_PROVIDER"))).replace(" ", "_").replace("/", "_").replace(".", "")
            emission_date = str(row.get("dataEmissao", "UNKNOWN_DATE")).replace(" ", "_").replace("/", "_").replace(".", "")
            document_value = str(row.get("valorDocumento", 0)).replace(".", "_")
            
            unique_expense_id = f"{provider_name}_{emission_date}_{document_value}"
            
            despesa_node = {
                "id": unique_expense_id,
                "dataEmissao": row.get("dataEmissao", ""),
                "ufFornecedor": row.get("deputado_siglaUf", ""),
                "categoria": row.get("tipoDespesa", "Outros"),
                "valorDocumento": float(row.get("valorDocumento", 0)),
                "nomeFornecedor": row.get("txtFornecedor", "N/A")
            }
            
            # Envia a despesa
            await client.post(f"{BACKEND_URL}/politician/{external_id}/despesa", json=despesa_node)
            
        except Exception as e:
            logger.error(f"Erro na ingestão para {external_id}: {e}")

async def ingest_camara_despesas():
    # O Client assíncrono gerencia o pool de conexões de forma eficiente
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Semáforo: Permite até 100 requisições simultâneas (ajuste conforme a capacidade da sua API)
        semaphore = asyncio.Semaphore(5) 
        politicians_processed = set()
        
        for ano in [2024, 2025]:
            file_path = Path(f"data/raw/camara/ceap_{ano}_raw.parquet")
            if not file_path.exists():
                logger.warning(f"Arquivo não encontrado: {file_path}")
                continue

            df = pl.read_parquet(file_path)
            logger.info(f"Ingerindo {len(df)} despesas da Câmara para {ano}...")

            # Cria uma lista de "tarefas" assíncronas para cada linha
            tasks = [
                process_row(client, semaphore, row, politicians_processed) 
                for row in df.to_dicts()
            ]
            
            # Executa todas as tarefas de forma concorrente
            await asyncio.gather(*tasks)
            logger.info(f"Ingestão do ano {ano} concluída.")

async def ingest_emendas():
    # Placeholder for emendas ingestion
    pass

async def main():
    await ingest_camara_despesas()
    await ingest_emendas()

if __name__ == "__main__":
    # Ponto de entrada para a execução assíncrona
    asyncio.run(main())