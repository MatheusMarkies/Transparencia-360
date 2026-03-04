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

def run_step(step_num: float, name: str, callable_fn):
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
    parser.add_argument("--keep-db", action="store_true", help="Pula o reset do DB, os downloads brutos e a fase de INSERT pesada")
    args = parser.parse_args()

    LIMIT = args.limit
    KEEP_DB = args.keep_db
    
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

    # Pre-step: Selective directory structure verification and Database Reset
    def setup_directories_and_db():
        base_path = Path(__file__).resolve().parent.parent / "data"
        dirs = [
             base_path / "downloads" / "diarios_oficiais",
             base_path / "downloads" / "notas_fiscais",
             base_path / "processed"
        ]
        
        if not KEEP_DB:
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
            
            # --- HARD RESET DO BANCO DE DADOS ---
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
        else:
            # Apenas garante que as pastas existem sem apagar os dados originais
            for d in dirs:
                if not d.exists():
                    d.mkdir(parents=True, exist_ok=True)
            logger.info("  ⏭️ Modo --keep-db ativado: Mantendo os arquivos em disco e pulando o Reset do Banco.")

    run_step(0, "Directory Setup & Database Reset", setup_directories_and_db)

    # Verifica se deve pular a fase inteira de Ingestão/Download
    if not KEEP_DB:
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
            for yr in [2022, 2023, 2024, 2025, 2026]:
                ExpensesWorker(year=yr).run(limit=LIMIT)
        run_step(4, "ExpensesWorker (Legacy Sync)", run_step_4_legacy)

        def run_step_5_legacy():
            from src.gatherers.absences_worker import AbsencesWorker
            AbsencesWorker(year=2024).run(limit=LIMIT)
        run_step(5, "AbsencesWorker", run_step_5_legacy)

        # Passo 6: Ingestão real dos dados em Parquet (A que demorava mais)
        #def ingestao_dados():
        #    from ingest_parquet import ingest_camara_despesas, ingest_emendas
        #    import asyncio
        #    
        #    async def run_ingestion():
        #        await ingest_camara_despesas()
        #        await ingest_emendas()
        #        
        #    asyncio.run(run_ingestion())
            
        #run_step(6, "Ingestão de Arquivos Parquet (Fase 2)", ingestao_dados)

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

    else:
        logger.info("\n⏭️ FASE 1 e FASE 2 PULADAS (--keep-db ativado).")
        logger.info("   Os dados brutos e os INSERTs milionários no banco já estão garantidos.")


    # =========================================================================
    # FASE 3: ANÁLISE, ENRIQUECIMENTO E GRAFOS (EXECUTA SEMPRE)
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

    #def step_13():
    #    from src.gatherers.emendas_gatherer import EmendasGatherer
    #    import requests
    #    import asyncio
    #    
    #    try:
    #        resp = requests.get("http://localhost:8080/api/v1/politicians/search?name=", timeout=30)
    #        if resp.status_code == 200:
    #            pols = resp.json()
    #           if pols:
    #                # ---> ADICIONE ESTA LINHA AQUI <---
    #                pols = sorted(pols, key=lambda k: str(k.get('name', '')))
    #                gatherer = EmendasGatherer(pols, limit=LIMIT)
    #                
    #                if asyncio.iscoroutinefunction(gatherer.run):
    #                    asyncio.run(gatherer.run())
    #                else:
    #                    try:
    #                        loop = asyncio.get_event_loop()
    #                    except RuntimeError:
    #                        loop = asyncio.new_event_loop()
    #                        asyncio.set_event_loop(loop)
    #                        
    #                    gatherer.run()
    #        else:
    #            logger.error(f"Step 13 failed: HTTP {resp.status_code}")
    #    except Exception as e:
    #        logger.error(f"Step 13 failed: {e}")
    #        
    #run_step(13, "EmendasGatherer (Data Extraction to Graph)", step_13)

    def step_14():
        from src.gatherers.emendas_pix_worker import EmendasPixWorker
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "admin123")
        w = EmendasPixWorker(neo4j_uri=uri, neo4j_user=user, neo4j_password=password)
        try: w.run()
        finally: w.close()
    run_step(14, "EmendasPixWorker (Circular Flow Anomaly Detection)", step_14)

    def step_14_5():
        from src.gatherers.pncp_worker import PNCPWorker
        w = PNCPWorker()
        w.run(limit=LIMIT)
    run_step(14.5, "PNCP Worker (Contratos de Municípios Alvo)", step_14_5)

    def step_15():
        """
        ROSIE — Full CEAP Anomaly Detection Engine
        
        Runs 12 classifiers on all CEAP receipts:
        1.  MealPriceOutlier      — Statistical outlier on meal expenses (IQR)
        2.  TravelSpeed            — Physically impossible trips (Haversine)
        3.  MonthlySubquotaLimit   — Over-limit spending per subcota
        4.  ElectionPeriod         — Spending during election campaigns
        5.  WeekendHoliday         — Expenses on non-working days
        6.  DuplicateReceipt       — Same receipt submitted twice (hash fingerprint)
        7.  CNPJBlacklist          — CEIS/CNEP blacklisted companies
        8.  CompanyAge             — Payments to very new companies
        9.  BenfordLaw             — Benford's Law digit distribution (Chi²)
        10. HighValueOutlier       — Global z-score anomaly detection
        11. SuspiciousSupplier     — Same supplier serving too many deputies
        12. SequentialReceipt      — Sequential nota fiscal numbers
        
        Outputs:
        - data/processed/rosie_report.json       (full structured report)
        - data/processed/rosie_anomalies.csv     (flat anomaly list)
        - data/processed/rosie_risk_ranking.txt  (human-readable ranking)
        - Backend API push (rosie risk scores per politician)
        """
        from src.gatherers.rosie_worker import RosieWorker
        worker = RosieWorker(years=[2023, 2024, 2025, 2026])
        worker.run(limit=LIMIT)
        
        # Inlined push_rosie_to_backend to fix python scope issues
        """Lê o CSV de anomalias da Rosie e injeta os totais reais no Backend Java."""
        import pandas as pd
        import requests
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("📡 Iniciando injeção dos dados da Rosie no Banco de Dados...")
        
        try:
            rosie_csv_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "rosie_anomalies.csv"
            df = pd.read_csv(rosie_csv_path)
            deputados = df['deputy_id'].unique()
            base_url = "http://localhost:8080/api/v1/politicians"
            
            for dep_id in deputados:
                anomalias_deputado = df[df['deputy_id'] == dep_id]
                contagem = anomalias_deputado['classifier'].value_counts().to_dict()
                
                benford = int(contagem.get('BenfordLawClassifier', 0))
                duplicatas = int(contagem.get('DuplicateReceiptClassifier', 0))
                fim_semana = int(contagem.get('WeekendHolidayClassifier', 0))
                saude_irregular = int(contagem.get('PersonalHealthExpenseClassifier', 0))
                luxo_pessoal = int(contagem.get('LuxuryPersonalExpenseClassifier', 0))
                
                ext_id = f"camara_{dep_id}"
                
                try:
                    resp = requests.get(f"{base_url}/external/{ext_id}")
                    if resp.status_code == 200:
                        pol = resp.json()
                        pol['rosieBenfordCount'] = benford
                        pol['rosieDuplicateCount'] = duplicatas
                        pol['rosieWeekendCount'] = fim_semana
                        pol['rosieHealthCount'] = saude_irregular
                        pol['rosieLuxuryCount'] = luxo_pessoal
                        
                        current_risk = pol.get('cabinetRiskScore') or 0
                        
                        dets = []
                        if pol.get('cabinetRiskDetails'):
                            try:
                                dets = json.loads(pol['cabinetRiskDetails'])
                            except:
                                pass
                                
                        if benford > 0:
                            current_risk = min(100, current_risk + 50)
                            dets.append({
                                "indicator": "Auditoria Matemática (ROSIE)",
                                "score": 50,
                                "description": f"Encontradas {benford} notas fiscais orgânicas com desvios na Lei de Benford (Possibilidade de fraudes manuais)."
                            })
                        if duplicatas > 0:
                            current_risk = min(100, current_risk + 20)
                            dets.append({
                                "indicator": "Auditoria Matemática (ROSIE)",
                                "score": 20,
                                "description": f"Encontrados {duplicatas} envios duplicados do mesmo recibo para ressarcimento."
                            })
                        if saude_irregular > 0:
                            current_risk = min(100, current_risk + 40)
                            dets.append({
                                "indicator": "Desvio de Fundo de Saúde",
                                "score": 40,
                                "description": f"Encontrados {saude_irregular} gastos com serviços médicos e estéticos proibidos na CEAP."
                            })
                        if luxo_pessoal > 0:
                            current_risk = min(100, current_risk + 30)
                            dets.append({
                                "indicator": "Desvio Imoral (Luxo)",
                                "score": 30,
                                "description": f"Encontrados {luxo_pessoal} pagamentos em Pet Shops, Joalherias ou Resorts."
                            })
                            
                        pol['cabinetRiskScore'] = current_risk
                        pol['cabinetRiskDetails'] = json.dumps(dets, ensure_ascii=False)
                        
                        update_resp = requests.post(base_url, json=pol)
                        if update_resp.status_code in [200, 201]:
                            logger.info(f"  ✅ Deputado {ext_id}: Integrado no Painel!")
                        else:
                            logger.error(f"  ❌ Erro ao enviar {ext_id}: HTTP {update_resp.status_code}")
                except Exception as e:
                    logger.error(f"Erro na requisição da API para {ext_id}: {e}")
        except Exception as e:
            logger.error(f"Falha ao ler rosie_anomalies.csv: {e}")
        except Exception as e:
            logger.error(f"Falha ao ler rosie_anomalies.csv: {e}. O motor da Rosie rodou?")
            
    run_step(15, "ROSIE — Full CEAP Anomaly Detection Engine", step_15)

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

    def step_25():
        import requests
        try:
            resp = requests.delete("http://localhost:8080/api/internal/workers/ingest/prune-empty", timeout=60)
            if resp.status_code == 200:
                logger.info(f"  Pruning successful: {resp.text}")
            else:
                logger.error(f"  Pruning failed: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"  Pruning error: {e}")
    run_step(25, "Database Pruning (Cleaning Ghost Records)", step_25)

    # NOVO: Super Relatório para Auditoria (Validação da Verdade)
    def step_26():
        from src.gatherers.super_report_worker import SuperReportWorker
        w = SuperReportWorker()
        w.run(limit=LIMIT)
    run_step(26, "SuperReportWorker (Gerador de Laudo JSON Unificado)", step_26)

    # =========================================================================
    # FECHAMENTO E RELATÓRIO
    # =========================================================================
    total_elapsed = time.time() - total_start
    pipeline_stats = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_minutes": round(total_elapsed / 60, 2),
        "target_limit": LIMIT,
        "keep_db_mode": KEEP_DB,
        "steps_executed": 26 if not KEEP_DB else 18,
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
    logger.info(f"    Keep DB Mode: {KEEP_DB}")
    logger.info(f"    Errors: {len(ERRORS)}")
    logger.info(f"    Total Processing Time: {total_elapsed/60:.1f} minutes")

if __name__ == "__main__":
    main()