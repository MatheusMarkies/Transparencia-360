import sys
import os
import time
import logging
import argparse
import traceback
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Ensure imports work
sys.path.append(str(Path(__file__).resolve().parent))

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
        logger.warning("  Get your key at: https://portaldatransparencia.gov.br/api-de-dados")
        logger.warning("!"*70 + "\n")

    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info(f"║  MASTER EXTRACTION v3.0 — {LIMIT} Politicians Pipeline      ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    total_start = time.time()

    # Pre-step: Selective directory structure verification
    def setup_directories():
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
                # Clean contents but preserve folders
                logger.info(f"Cleaning existing directory: {d}")
                for item in d.iterdir():
                    if item.is_file(): item.unlink()
                    elif item.is_dir(): shutil.rmtree(item)
        logger.info("  ✅ Data directory structure verified and cleaned.")
    run_step(0, "Directory Setup & selective Cleanup", setup_directories)

    # Step 1: Base deputy data
    def step_1():
        from src.gatherers.camara_gatherer import CamaraGatherer
        g = CamaraGatherer()
        g.fetch_and_ingest_deputies(page=1, fetch_items=LIMIT)
    run_step(1, "CamaraGatherer (Base Data)", step_1)

    # Step 2: Base senator data (REMOVED as per user request)
    # def step_2():
    #     from src.gatherers.senado_gatherer import SenadoGatherer
    #     g = SenadoGatherer()
    #     g.fetch_and_ingest_senators()
    # run_step(2, "SenadoGatherer (Base Data)", step_2)

    # --- GROUP A: Parallel Independent Enrichment ---
    logger.info("\n🚀 Running Group A: Independent Enrichment (Parallel)...")
    
    def run_step_3():
        from src.gatherers.transparencia_worker import TransparenciaWorker
        TransparenciaWorker(year=2025).run(limit=LIMIT)
        
    def run_step_4():
        from src.gatherers.expenses_worker import ExpensesWorker
        # Multi-year check: 2024 & 2025
        for yr in [2024, 2025]:
            ExpensesWorker(year=yr).run(limit=LIMIT)
            
    def run_step_5():
        from src.gatherers.absences_worker import AbsencesWorker
        AbsencesWorker(year=2024).run(limit=LIMIT)
        
    def run_step_6():
        from src.gatherers.state_affinity_worker import StateAffinityWorker
        StateAffinityWorker().run(limit=LIMIT)
        
    def run_step_7():
        from src.gatherers.tse_worker import TSEWorker
        TSEWorker().run(limit=LIMIT)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(run_step, 3, "TransparenciaWorker", run_step_3),
            executor.submit(run_step, 4, "ExpensesWorker (2024-2025)", run_step_4),
            executor.submit(run_step, 5, "AbsencesWorker", run_step_5),
            executor.submit(run_step, 6, "StateAffinityWorker", run_step_6),
            executor.submit(run_step, 7, "TSEWorker", run_step_7)
        ]
        [f.result() for f in futures]

    # --- GROUP B: Parallel Analytical Steps ---
    logger.info("\n🚀 Running Group B: Analytical Detectors (Parallel)...")
    
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

    # Step 10: Rachadinha Scoring v2.0 (Sequential, heavy)
    def step_10():
        from src.gatherers.rachadinha_worker import RachadinhaScoringWorker
        w = RachadinhaScoringWorker()
        w.run(limit=LIMIT, enable_nlp=True, enable_judicial=True)
    run_step(10, "RachadinhaScoringWorker v2.0 (Risk Score)", step_10)

    # Step 12: Cross-Match Orchestrator (Graph Deep Web)
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

    # Step 13-14: Emendas Data
    def step_13():
        from src.gatherers.emendas_gatherer import EmendasGatherer
        import requests
        try:
            resp = requests.get("http://localhost:8080/api/v1/politicians/search?name=", timeout=30)
            if resp.status_code == 200:
                pols = resp.json()
                if pols:
                    EmendasGatherer(pols, limit=LIMIT).run()
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

    # Step 16: Coherence Worker
    def step_16():
        from src.nlp.coherence_worker import CoherenceWorker
        CoherenceWorker().run()
    run_step(16, "CoherenceWorker (Promises vs. Votes Alignment)", step_16)

    # Step 17-18: Gazette Pipeline
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
    run_step(18, "GazetteAggregator (Neo4j Findings \u2192 Core API)", step_18)

    # NEW Step 19: Deduplication
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

    # NEW Step 20: Judicial Aggregator
    def step_20():
        from src.gatherers.judicial_aggregator_worker import JudicialAggregatorWorker
        w = JudicialAggregatorWorker()
        w.run(limit=LIMIT)
    run_step(20, "JudicialAggregator (DataJud Findings \u2192 Core API)", step_20)

    # Step 21: Documentary Evidence Worker (Phase 1 Motor)
    def step_21():
        from src.gatherers.documentary_evidence_worker import DocumentaryEvidenceWorker
        w = DocumentaryEvidenceWorker()
        w.run(limit=LIMIT)
    run_step(21, "DocumentaryEvidenceWorker (Deterministic NLP & Audit Trail)", step_21)

    total_elapsed = time.time() - total_start
    pipeline_stats = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_minutes": round(total_elapsed / 60, 2),
        "target_limit": LIMIT,
        "steps_executed": 21,
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
    logger.info(f"  PIPELINE COMPLETE \u2014 {total_elapsed/60:.1f} minutes total")
    logger.info(f"{'='*70}")
    
    if ERRORS:
        logger.warning(f"\n  \u26a0\ufe0f {len(ERRORS)} ERRORS ENCOUNTERED:")
        for e in ERRORS:
            logger.warning(f"    \u2192 {e}")
    else:
        logger.info("  \u2705 All 20 steps completed successfully!")

    logger.info(f"\n  Final Statistics:")
    logger.info(f"    Politicians Target: {LIMIT}")
    logger.info(f"    Steps Executed: 20")
    logger.info(f"    Errors: {len(ERRORS)}")
    logger.info(f"    Total Processing Time: {total_elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
