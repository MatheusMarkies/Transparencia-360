# Pipeline de Integração das Novas Camadas
import os
import sys
import logging
from pathlib import Path
import asyncio

# Setup path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ARCH_ALIGN")

async def run_arch_alignment_extraction():
    logger.info("Starting Architecture-Aligned Extraction (Layer 1)...")
    
    # 1. Caixa Quente (APIs)
    from extractors.camara_deputados import extrair_despesas_ceap, extrair_presencas
    from extractors.portal_transparencia import extrair_emendas, extrair_servidores
    from extractors.querido_diario import extrair_dispensas_licitacao
    
    tasks = [
        extrair_despesas_ceap(limit=50),
        extrair_presencas("2025-01-01", "2025-03-01"),
        extrair_emendas(2025),
        extrair_servidores(),
        extrair_dispensas_licitacao(["3550308"], "2025-01-01") # SP Capital
    ]
    
    await asyncio.gather(*tasks)
    logger.info("Layer 1 (Caixa Quente) ingestion to Parquet complete.")

def run_arch_alignment_etl():
    logger.info("Starting Architecture-Aligned ETL (Layer 2 - Caixa Fria)...")
    
    from etl.receita_federal import processar_socios, processar_empresas, processar_estabelecimentos
    from etl.tse import processar_doacoes, processar_bens
    
    processar_socios()
    processar_empresas()
    processar_estabelecimentos()
    
    for year in [2014, 2018, 2022]:
        processar_doacoes(year)
        processar_bens(year)
        
    logger.info("Layer 2 (Caixa Fria) Parquet processing complete.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_arch_alignment_extraction())
    run_arch_alignment_etl()
