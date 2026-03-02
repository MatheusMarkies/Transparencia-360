import sys
import os
import time
import logging
import argparse
import traceback
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Injetando a chave da API fornecida
os.environ["PORTAL_API_KEY"] = "7c582554ddd97a21198f7bd9c1d4d4e9"
os.environ["NEO4J_PASSWORD"] = "admin123"

# Ensure imports work
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent))

from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MASTER_EXTRACTION")

ERRORS = []

def run_step(step_num: int, name: str, callable_fn):
    """Run a single extraction step with error handling and timing."""
    logger.info(f"\n{'='*70}")
    logger.info(f"  STEP {step_num}: {name}")
    logger.info(f"{'='*70}")
    start = time.time()
    try:
        callable_fn()
        elapsed = time.time() - start
        logger.info(f"  ✅ {name} completed in {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        error_msg = f"STEP {step_num} ({name}): {type(e).__name__}: {e}"
        logger.error(f"  ❌ {error_msg}")
        logger.error(traceback.format_exc())
        ERRORS.append(error_msg)

def main():
    parser = argparse.ArgumentParser(description="Run the full Extractions pipeline.")
    parser.add_argument("--limit", type=int, default=100, help="Number of parliamentarians to process")
    args = parser.parse_args()

    LIMIT = args.limit
    
    # Check for API Keys
    portal_key = os.getenv("PORTAL_API_KEY")
    if not portal_key:
        logger.warning("\n" + "!"*70)
        logger.warning("  ⚠️ WARNING: 'PORTAL_API_KEY' environment variable not found.")
        logger.warning("  Some steps (Emendas, Transparency) will be skipped or limited.")
        logger.warning("!"*70 + "\n")

    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info(f"║  MASTER EXTRACTION v3.1 — {LIMIT} Politicians Pipeline      ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    total_start = time.time()

    # Pre-step: Selective directory structure verification
# Pre-step: Selective directory structure verification and Database Reset
    def setup_directories_and_db():
        base_path = Path(__file__).resolve().parent.parent / "data"
        dirs = [
             base_path / "downloads" / "diarios_oficiais",
             base_path / "downloads" / "notas_fiscais",
             base_path / "processed"
        ]
        for d in dirs:
            if not d.exists():
                logger.info(f"Creating missing directory: {d}")
                d.mkdir(parents=True, exist_ok=True)
            else:
                logger.info(f"Cleaning existing directory: {d}")
                for item in d.iterdir():
                    if item.is_file(): item.unlink()
                    elif item.is_dir(): shutil.rmtree(item)
        logger.info("  ✅ Data directory structure verified and cleaned.")
        
        # --- NOVO: HARD RESET DO BANCO DE DADOS ---
# --- NOVO: HARD RESET DO BANCO DE DADOS ---
        import requests
        logger.info("  🔄 Enviando comando de HARD RESET para os Bancos de Dados (PostgreSQL + Neo4j)...")
        try:
            # 1. Limpa o Neo4j (Grafos)
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "admin123")
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            driver.close()
            logger.info("  ✅ Banco de Grafos (Neo4j) zerado com sucesso.")
            
            # 2. Limpa o PostgreSQL (Relacional) via API
            resp = requests.delete("http://localhost:8080/api/internal/workers/ingest/reset-database", timeout=15)
            if resp.status_code == 200:
                logger.info("  ✅ Banco Relacional (PostgreSQL) zerado com sucesso.")
            else:
                logger.warning(f"  ⚠️ Falha ao zerar PostgreSQL. API retornou HTTP {resp.status_code}")
            
        except Exception as e:
            logger.warning(f"  ⚠️ Não foi possível limpar os bancos de dados automaticamente: {e}")

    run_step(0, "Directory Setup & Database Reset", setup_directories_and_db)

    # =========================================================================
    # FASE 1: EXTRAÇÃO DE DADOS (DOWNLOADS PARA O DISCO)
    # =========================================================================
    logger.info("\n🚀 FASE 1: Extração de Dados (Paralela)...")

    def step_1():
        from src.gatherers.camara_gatherer import CamaraGatherer
        g = CamaraGatherer()
        g.fetch_and_ingest_deputies(page=1, fetch_items=LIMIT)
    run_step(1, "CamaraGatherer (Base Data)", step_1)

    def run_step_1_new():
        from extractors.camara_deputados import extrair_despesas_ceap, extrair_presencas
        import asyncio
        asyncio.run(extrair_despesas_ceap(limit=LIMIT))
        asyncio.run(extrair_presencas("2025-01-01", "2025-03-01"))
    
    def run_step_3_new():
        from extractors.portal_transparencia import extrair_emendas, extrair_servidores
        import asyncio
        asyncio.run(extrair_emendas(2025))
        asyncio.run(extrair_servidores())

    def run_step_7_new():
        from etl.tse import processar_doacoes, processar_bens
        for yr in [2014, 2018, 2022]:
            processar_doacoes(yr)
            processar_bens(yr)

    def run_step_22_new():
        from etl.receita_federal import processar_socios, processar_empresas
        processar_socios()
        processar_empresas()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(run_step, 2, "Camara Extractors (CEAP/Presenças)", run_step_1_new),
            executor.submit(run_step, 3, "Portal Transparência Extractors", run_step_3_new),
            executor.submit(run_step, 7, "TSE ETL (Massive Dumps)", run_step_7_new),
            executor.submit(run_step, 22, "Receita Federal ETL (QSA/Empresas)", run_step_22_new)
        ]
        [f.result() for f in futures]

    # =========================================================================
    # FASE 2: INGESTÃO E LIMPEZA DE DADOS
    # =========================================================================
    logger.info("\n🚀 FASE 2: Ingestão de Dados (Carga na API/DB)...")

    def run_step_4_legacy():
        from src.gatherers.expenses_worker import ExpensesWorker
        for yr in [2024, 2025]:
            ExpensesWorker(year=yr).run(limit=LIMIT)
    run_step(4, "ExpensesWorker (Legacy Sync)", run_step_4_legacy)

    def run_step_5_legacy():
        from src.gatherers.absences_worker import AbsencesWorker
        AbsencesWorker(year=2024).run(limit=LIMIT)
    run_step(5, "AbsencesWorker", run_step_5_legacy)

    # NOVO PASSO 6: Chamando a ingestão real dos dados em Parquet
    def ingestao_dados():
        # Importando as funções corretas do seu arquivo ingest_parquet.py
        from ingest_parquet import ingest_camara_despesas, ingest_emendas
        import asyncio
        
        async def run_ingestion():
            await ingest_camara_despesas()
            await ingest_emendas()
            
        # Executa o envio dos dados do disco para a API de forma assíncrona
        asyncio.run(run_ingestion())
        
    run_step(6, "Ingestão de Arquivos Parquet (Fase 2)", ingestao_dados)

    def step_19():
        import requests
        try:
            resp = requests.post("http://localhost:8080/api/internal/workers/ingest/deduplicate", timeout=60)
            if resp.status_code == 200:
                logger.info(f"  Deduplication successful: {resp.text}")
            else:
                logger.error(f"  Deduplication failed: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"  Deduplication error: {e}")
    run_step(19, "Backend Deduplication (Data Integrity)", step_19)

    # =========================================================================
    # FASE 3: ANÁLISE, ENRIQUECIMENTO E GRAFOS
    # =========================================================================
    logger.info("\n🚀 FASE 3: Análises Analíticas e Grafos...")

    def run_step_8():
        from src.gatherers.wealth_anomaly_worker import WealthAnomalyWorker
        WealthAnomalyWorker().run(limit=LIMIT)
        
    def run_step_9():
        from src.gatherers.staff_anomaly_worker import StaffAnomalyWorker
        StaffAnomalyWorker().run(limit=LIMIT)
        
    def run_step_11():
        from src.gatherers.spatial_anomaly_worker import SpatialAnomalyWorker
        SpatialAnomalyWorker().run(limit=LIMIT)
        
    def run_step_15():
        from src.gatherers.camara_nlp_gatherer import CamaraNLPGatherer
        CamaraNLPGatherer().run(limit=LIMIT)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(run_step, 8, "WealthAnomalyWorker", run_step_8),
            executor.submit(run_step, 9, "StaffAnomalyWorker", run_step_9),
            executor.submit(run_step, 11, "SpatialAnomalyWorker", run_step_11),
            executor.submit(run_step, 15, "CamaraNLPGatherer", run_step_15)
        ]
        [f.result() for f in futures]

    def step_10():
        from src.gatherers.rachadinha_worker import RachadinhaScoringWorker
        w = RachadinhaScoringWorker()
        w.run(limit=LIMIT, enable_nlp=True, enable_judicial=True)
    run_step(10, "RachadinhaScoringWorker v2.0 (Risk Score)", step_10)

    def step_12():
        from src.gatherers.cross_match_orchestrator import CrossMatchOrchestrator
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "admin123")
        driver = None
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                w = CrossMatchOrchestrator(neo4j_session=session)
                w.run(limit=LIMIT)
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j. Dry Run Orthogonal Mode. {e}")
            w = CrossMatchOrchestrator(neo4j_session=None)
            w.run(limit=LIMIT)
        finally:
            if driver: driver.close()
    run_step(12, "CrossMatchOrchestrator (Deep Neo4j Graph Builder)", step_12)

    def step_13():
        from src.gatherers.emendas_gatherer import EmendasGatherer
        import requests
        import asyncio
        
        try:
            resp = requests.get("http://localhost:8080/api/v1/politicians/search?name=", timeout=30)
            if resp.status_code == 200:
                pols = resp.json()
                if pols:
                    gatherer = EmendasGatherer(pols, limit=LIMIT)
                    
                    # Verifica se o método run é nativamente assíncrono (async def run)
                    if asyncio.iscoroutinefunction(gatherer.run):
                        asyncio.run(gatherer.run())
                    else:
                        # Se for síncrono mas precisar de um Event Loop interno
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                        gatherer.run()
            else:
                logger.error(f"Step 13 failed: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Step 13 failed: {e}")
            
    run_step(13, "EmendasGatherer (Data Extraction to Graph)", step_13)

    def step_14():
        from src.gatherers.emendas_pix_worker import EmendasPixWorker
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "admin123")
        w = EmendasPixWorker(neo4j_uri=uri, neo4j_user=user, neo4j_password=password)
        try: w.run()
        finally: w.close()
    run_step(14, "EmendasPixWorker (Circular Flow Anomaly Detection)", step_14)

    def step_16():
        from src.nlp.coherence_worker import CoherenceWorker
        CoherenceWorker().run()
    run_step(16, "CoherenceWorker (Promises vs. Votes Alignment)", step_16)

    def step_17():
        from src.nlp.gazette_text_fetcher import GazetteTextFetcher
        from src.nlp.gazette_neo4j_ingester import GazetteNeo4jIngester
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "admin123")
        driver = None
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                fetcher = GazetteTextFetcher()
                ingester = GazetteNeo4jIngester(neo4j_session=session)
                ingester.create_gazette_constraints()
                results = fetcher.search_and_extract(query="dispensa de licitação", since="2024-01-01", max_results=20)
                ingester.ingest_batch(results)
        except Exception as e:
            logger.error(f"Step 17 failed: {e}")
        finally:
            if driver: driver.close()
    run_step(17, "GazetteGraphBuilder (Neo4j Deep Web Expansion)", step_17)
    
    def step_18():
        from src.nlp.gazette_aggregator_worker import GazetteAggregatorWorker
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "admin123")
        w = GazetteAggregatorWorker(neo4j_uri=uri, neo4j_user=user, neo4j_password=password)
        try: w.run(limit=LIMIT)
        finally: w.close()
    run_step(18, "GazetteAggregator (Neo4j Findings → Core API)", step_18)

    def step_20():
        from src.gatherers.judicial_aggregator_worker import JudicialAggregatorWorker
        w = JudicialAggregatorWorker()
        w.run(limit=LIMIT)
    run_step(20, "JudicialAggregator (DataJud Findings → Core API)", step_20)

    def step_21():
        from src.gatherers.documentary_evidence_worker import DocumentaryEvidenceWorker
        w = DocumentaryEvidenceWorker()
        w.run(limit=LIMIT)
    run_step(21, "DocumentaryEvidenceWorker (Deterministic NLP & Audit Trail)", step_21)

    def step_23():
        from src.gatherers.rais_worker import RAISWorker
        RAISWorker().run()
    run_step(23, "RAISWorker (Ghost Employee Detection)", step_23)

    def step_24():
        from src.gatherers.tcu_worker import TCUWorker
        TCUWorker().run()
    run_step(24, "TCUWorker (Irregular Accounts Monitoring)", step_24)

    # =========================================================================
    # FECHAMENTO E RELATÓRIO
    # =========================================================================
    total_elapsed = time.time() - total_start
    pipeline_stats = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_minutes": round(total_elapsed / 60, 2),
        "target_limit": LIMIT,
        "steps_executed": 24,
        "errors_count": len(ERRORS),
        "errors_details": ERRORS
    }
    
    try:
        stats_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "pipeline_summary.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            import json
            json.dump(pipeline_stats, f, indent=2)
        logger.info(f"  ✅ Optimization Report saved to: {stats_path}")
    except Exception as e:
        logger.error(f"  Failed to save summary: {e}")
        
    logger.info(f"\n{'='*70}")
    logger.info(f"  PIPELINE COMPLETE — {total_elapsed/60:.1f} minutes total")
    logger.info(f"{'='*70}")
    
    if ERRORS:
        logger.warning(f"\n  ⚠️ {len(ERRORS)} ERRORS ENCOUNTERED:")
        for e in ERRORS:
            logger.warning(f"    → {e}")
    else:
        logger.info("  ✅ All steps completed successfully!")

    logger.info(f"\n  Final Statistics:")
    logger.info(f"    Politicians Target: {LIMIT}")
    logger.info(f"    Errors: {len(ERRORS)}")
    logger.info(f"    Total Processing Time: {total_elapsed/60:.1f} minutes")

if __name__ == "__main__":
    main()