import polars as pl
import httpx
import logging
import asyncio
import time
from pathlib import Path

# ==============================
# LOGGING
# ==============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# remove spam HTTP
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BACKEND_URL = "http://localhost:8080/api/internal/workers/ingest"

# ==============================
# CONFIG
# ==============================

NUM_WORKERS = 10
QUEUE_SIZE = 1000
HTTP_TIMEOUT = 15.0
MAX_RETRIES = 3


# ==============================
# PROGRESS TRACKER
# ==============================

class ProgressTracker:

    def __init__(self, total):
        self.total = total
        self.processed = 0
        self.start_time = time.time()
        self.lock = asyncio.Lock()

    async def increment(self):
        async with self.lock:
            self.processed += 1

            if self.processed % 1000 == 0 or self.processed == self.total:
                elapsed = time.time() - self.start_time
                rate = self.processed / elapsed if elapsed else 0

                remaining = self.total - self.processed
                eta = remaining / rate if rate else 0

                percent = (self.processed / self.total) * 100

                logger.info(
                    f"[INGESTÃO] "
                    f"{self.processed}/{self.total} "
                    f"({percent:.2f}%) | "
                    f"{rate:.0f} reg/s | "
                    f"ETA: {eta:.0f}s"
                )


# ==============================
# SAFE POST
# ==============================

async def safe_post(client, url, payload):

    for attempt in range(MAX_RETRIES):
        try:
            r = await client.post(url, json=payload)

            if r.status_code < 300:
                return True

        except Exception:
            pass

        await asyncio.sleep(2 ** attempt)

    return False


# ==============================
# PROCESS ROW
# ==============================

# ==============================
# PROCESS ROW
# ==============================

async def process_row(
    client,
    row,
    politicians_processed,
    pol_lock,
    progress: ProgressTracker,
):

    external_id = f"camara_{row['deputado_id']}"

    # garante político único
    async with pol_lock:
        is_new = external_id not in politicians_processed
        if is_new:
            politicians_processed.add(external_id)

    if is_new:
        politician_data = {
            "externalId": external_id,
            "name": row["deputado_nome"],
            "party": row["deputado_siglaPartido"],
            "state": row["deputado_siglaUf"],
            "position": "Deputado Federal",
        }

        await safe_post(
            client,
            f"{BACKEND_URL}/politician",
            politician_data,
        )

    # CORREÇÃO: Lê as chaves corretas da API v2 ('nomeFornecedor', 'dataDocumento', 'valorLiquido')
    raw_provider = row.get("nomeFornecedor", row.get("txtFornecedor", "Fornecedor Desconhecido"))
    provider_safe = str(raw_provider).replace(" ", "_").replace("/", "_").replace(".", "")

    raw_date = row.get("dataDocumento", row.get("dataEmissao", "SEM_DATA"))
    # Algumas datas vêm com timestamp (ex: 2025-02-10T00:00:00), vamos cortar apenas o YYYY-MM-DD
    if isinstance(raw_date, str) and "T" in raw_date:
        raw_date = raw_date.split("T")[0]
        
    date_safe = str(raw_date).replace(" ", "_").replace("/", "_").replace(".", "")

    raw_value = row.get("valorLiquido", row.get("valorDocumento", 0))
    value_safe = str(raw_value).replace(".", "_")

    expense_id = f"{provider_safe}_{date_safe}_{value_safe}"

    despesa = {
        "id": expense_id,
        "dataEmissao": raw_date if raw_date != "SEM_DATA" else "",
        "ufFornecedor": row.get("siglaUF", row.get("deputado_siglaUf", "NA")),
        "categoria": row.get("tipoDespesa", "Outros"),
        "valorDocumento": float(raw_value),
        "nomeFornecedor": raw_provider,
    }

    await safe_post(
        client,
        f"{BACKEND_URL}/politician/{external_id}/despesa",
        despesa,
    )

    await progress.increment()


# ==============================
# WORKER
# ==============================

async def worker(
    wid,
    queue,
    client,
    politicians_processed,
    pol_lock,
    progress,
):

    logger.info(f"Worker {wid} iniciado")

    while True:
        row = await queue.get()

        if row is None:
            queue.task_done()
            break

        try:
            await process_row(
                client,
                row,
                politicians_processed,
                pol_lock,
                progress,
            )
        except Exception as e:
            logger.error(e)

        queue.task_done()

    logger.info(f"Worker {wid} finalizado")


# ==============================
# INGESTÃO
# ==============================

async def ingest_camara_despesas():

    # --------------------------
    # CARREGA DADOS
    # --------------------------

    all_rows = []

    for ano in [2024, 2025]:
        file = Path(__file__).resolve().parent.parent / "data" / "processed" / f"ceap_{ano}_raw.parquet"

        if file.exists():
            df = pl.read_parquet(file)
            all_rows.extend(df.to_dicts())

    total = len(all_rows)

    logger.info(f"Total de despesas: {total}")

    progress = ProgressTracker(total)

    queue = asyncio.Queue(maxsize=QUEUE_SIZE)

    politicians_processed = set()
    pol_lock = asyncio.Lock()

    limits = httpx.Limits(
        max_connections=50,
        max_keepalive_connections=20,
    )

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        limits=limits
    ) as client:

        workers = [
            asyncio.create_task(
                worker(
                    i,
                    queue,
                    client,
                    politicians_processed,
                    pol_lock,
                    progress,
                )
            )
            for i in range(NUM_WORKERS)
        ]

        # producer
        for row in all_rows:
            await queue.put(row)

        # stop workers
        for _ in workers:
            await queue.put(None)

        await queue.join()
        await asyncio.gather(*workers)

    logger.info("✅ INGESTÃO FINALIZADA")


async def ingest_emendas():
    logger.info("Ingestão de emendas ainda não implementada")

# ==============================
# MAIN
# ==============================

async def main():
    await ingest_camara_despesas()


if __name__ == "__main__":
    asyncio.run(main())