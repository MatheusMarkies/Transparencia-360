# etl/tse.py
import polars as pl
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/tse")
CLEAN_DIR = Path("data/clean/tse")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

def processar_doacoes(ano: int):
    """Processa doações. Alimenta: Módulo 1, 5, 6."""
    logger.info(f"Processando doações eleitorais do ano {ano}...")
    file_path = RAW_DIR / f"receitas_candidatos_{ano}.csv"
    if not file_path.exists():
        logger.warning(f"Arquivo não encontrado: {file_path}")
        return None

    df = pl.scan_csv(
        file_path,
        separator=";", encoding="latin1",
    ).select([
        pl.col("SQ_CANDIDATO").alias("sq_candidato"), 
        pl.col("NR_CPF_CNPJ_DOADOR").alias("doc_doador"), 
        pl.col("NM_DOADOR").alias("nome_doador"),
        pl.col("VR_RECEITA").alias("valor"), 
        pl.col("DS_FONTE_RECEITA").alias("fonte"), 
        pl.col("DT_RECEITA").alias("data"),
    ]).with_columns([
        pl.col("doc_doador").str.replace_all(r"[.\-/]", "").alias("doc_doador_limpo"),
        pl.col("valor").str.replace(",", ".").cast(pl.Float64, strict=False),
        pl.col("nome_doador").str.to_uppercase(),
    ]).collect()
    
    output_path = CLEAN_DIR / f"doacoes_{ano}_clean.parquet"
    df.write_parquet(output_path)
    logger.info(f"Salvas {len(df)} doações em {output_path}")
    return df

def processar_bens(ano: int):
    """Processa declaração de bens. Alimenta: Módulo 7."""
    logger.info(f"Processando declaração de bens do ano {ano}...")
    file_path = RAW_DIR / f"bem_candidato_{ano}.csv"
    if not file_path.exists():
        logger.warning(f"Arquivo não encontrado: {file_path}")
        return None

    df = pl.scan_csv(
        file_path,
        separator=";", encoding="latin1",
    ).select([
        pl.col("SQ_CANDIDATO").alias("sq_candidato"), 
        pl.col("DS_TIPO_BEM_CANDIDATO").alias("tipo_bem"), 
        pl.col("VR_BEM_CANDIDATO").alias("valor"),
    ]).with_columns([
        pl.col("valor").str.replace(",", ".").cast(pl.Float64, strict=False),
    ]).collect()
    
    output_path = CLEAN_DIR / f"bens_{ano}_clean.parquet"
    df.write_parquet(output_path)
    logger.info(f"Salvas {len(df)} declarações de bens em {output_path}")
    return df

if __name__ == "__main__":
    for year in [2014, 2018, 2022]:
        processar_doacoes(year)
        processar_bens(year)
