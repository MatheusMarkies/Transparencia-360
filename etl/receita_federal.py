# etl/receita_federal.py
import polars as pl
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/receita")
CLEAN_DIR = Path("data/clean/receita")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

def processar_socios():
    """Processa QSA — coração do Deep Proxy Mapping (Módulo 6)."""
    logger.info("Processando Quadros Societários (Socios)...")
    files = list(RAW_DIR.glob("Socios*.csv"))
    if not files:
        logger.warning("Nenhum arquivo Socios*.csv encontrado em data/raw/receita")
        return None

    df = pl.scan_csv(
        files,
        separator=";", encoding="latin1", has_header=False,
        new_columns=[
            "cnpj_basico", "identificador_socio", "nome_socio",
            "cpf_cnpj_socio", "qualificacao_socio", "data_entrada",
            "pais", "representante_legal", "nome_representante",
            "qualificacao_representante", "faixa_etaria"
        ]
    ).with_columns([
        pl.col("cnpj_basico").str.strip_chars(),
        pl.col("nome_socio").str.strip_chars().str.to_uppercase(),
        pl.col("cpf_cnpj_socio").str.strip_chars().str.replace_all(r"[.\-/]", ""),
    ]).filter(
        pl.col("cnpj_basico").str.len_chars() >= 8
    ).collect()
    
    output_path = CLEAN_DIR / "socios_clean.parquet"
    df.write_parquet(output_path)
    logger.info(f"Salvo {len(df)} registros de sócios em {output_path}")
    return df

def processar_empresas():
    """Processa empresas — identifica 'recém-nascidas' (Módulo 2)."""
    logger.info("Processando base de Empresas...")
    files = list(RAW_DIR.glob("Empresas*.csv"))
    if not files:
        logger.warning("Nenhum arquivo Empresas*.csv encontrado em data/raw/receita")
        return None

    df = pl.scan_csv(
        files,
        separator=";", encoding="latin1", has_header=False,
        new_columns=[
            "cnpj_basico", "razao_social", "natureza_juridica",
            "qualificacao_responsavel", "capital_social", "porte_empresa",
            "ente_federativo"
        ]
    ).with_columns([
        pl.col("cnpj_basico").str.strip_chars(),
        pl.col("razao_social").str.strip_chars().str.to_uppercase(),
        pl.col("capital_social").str.replace(",", ".").cast(pl.Float64, strict=False),
    ]).collect()
    
    output_path = CLEAN_DIR / "empresas_clean.parquet"
    df.write_parquet(output_path)
    logger.info(f"Salvo {len(df)} registros de empresas em {output_path}")
    return df

def processar_estabelecimentos():
    """Processa estabelecimentos — data de abertura e geolocalização."""
    logger.info("Processando base de Estabelecimentos...")
    files = list(RAW_DIR.glob("Estabelecimentos*.csv"))
    if not files:
        logger.warning("Nenhum arquivo Estabelecimentos*.csv encontrado em data/raw/receita")
        return None

    df = pl.scan_csv(
        files,
        separator=";", encoding="latin1", has_header=False,
        new_columns=[
            "cnpj_basico", "cnpj_ordem", "cnpj_dv", "identificador_matriz",
            "nome_fantasia", "situacao_cadastral", "data_situacao",
            "motivo_situacao", "nome_cidade_exterior", "pais",
            "data_inicio_atividade", "cnae_fiscal_principal", "cnae_fiscal_secundaria",
            "tipo_logradouro", "logradouro", "numero", "complemento",
            "bairro", "cep", "uf", "municipio",
            "ddd1", "telefone1", "ddd2", "telefone2",
            "ddd_fax", "fax", "email"
        ]
    ).with_columns([
        (pl.col("cnpj_basico").str.strip_chars()
         + pl.col("cnpj_ordem").str.strip_chars()
         + pl.col("cnpj_dv").str.strip_chars()
        ).alias("cnpj_completo"),
    ]).collect()
    
    output_path = CLEAN_DIR / "estabelecimentos_clean.parquet"
    df.write_parquet(output_path)
    logger.info(f"Salvo {len(df)} registros de estabelecimentos em {output_path}")
    return df

if __name__ == "__main__":
    processar_socios()
    processar_empresas()
    processar_estabelecimentos()
