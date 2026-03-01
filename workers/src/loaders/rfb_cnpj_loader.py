"""
Receita Federal - Base Completa de CNPJs (Batch Loader)
Source: https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj

Ingestão massiva do Quadro de Sócios e Administradores (QSA), Empresas,
e Estabelecimentos do dump público da Receita Federal (dezenas de GB em CSV).

Download Pattern:
  - Empresas*.csv   → Dados cadastrais básicos (CNPJ, Razão Social, Natureza Jurídica)
  - Socios*.csv     → QSA (Quadro de Sócios e Administradores)
  - Estabelecimentos*.csv → Endereço, CNAE, situação cadastral

Arquivos são particionados (Empresas0.csv .. Empresas9.csv).
Cada parte pode ter centenas de MB.

Estratégia: streaming line-by-line com batched Neo4j UNWIND para não
estourar a memória do Docker local.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import csv
import logging
import time
import requests
import zipfile
from typing import Optional, Generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Receita Federal dump download base
RFB_BASE_URL = "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/"

# File naming pattern: Empresas0.zip .. Empresas9.zip, Socios0.zip .. Socios9.zip
RFB_PARTITIONS = 10

# CSV Column indexes (Socios*.csv)
# The Receita Federal CSV uses semicolon delimiter and specific column order
SOCIOS_COLUMNS = {
    "cnpj_basico": 0,
    "identificador_socio": 1,      # 1=PJ, 2=PF, 3=Estrangeiro
    "nome_socio": 2,
    "cnpj_cpf_socio": 3,
    "qualificacao_socio": 4,
    "data_entrada_sociedade": 5,
    "pais": 6,
    "representante_legal": 7,
    "nome_representante": 8,
    "qualificacao_representante": 9,
    "faixa_etaria": 10
}

EMPRESAS_COLUMNS = {
    "cnpj_basico": 0,
    "razao_social": 1,
    "natureza_juridica": 2,
    "qualificacao_responsavel": 3,
    "capital_social": 4,
    "porte_empresa": 5,         # 00=Não informado, 01=ME, 03=EPP, 05=Demais
    "ente_federativo": 6
}

BATCH_SIZE = 1000  # Records per Neo4j UNWIND batch


class RFBCNPJLoader:
    """
    Processa os dumps CSV da Receita Federal e alimenta o Neo4j
    com nós de Empresa e Pessoa e relações SOCIO_ADMINISTRADOR_DE.
    """
    def __init__(self, data_dir: str = "/tmp/rfb_data", neo4j_session=None):
        self.data_dir = data_dir
        self.neo4j_session = neo4j_session
        os.makedirs(data_dir, exist_ok=True)

    # ── Download ────────────────────────────────────────────────────
    def download_partition(self, file_type: str, partition: int) -> Optional[str]:
        """
        Baixa uma partição. file_type: 'Socios', 'Empresas', 'Estabelecimentos'
        """
        filename = f"{file_type}{partition}"
        zip_path = os.path.join(self.data_dir, f"{filename}.zip")
        csv_path = os.path.join(self.data_dir, f"{filename}.csv")

        if os.path.exists(csv_path):
            logger.info(f"  ✅ {filename}.csv já existe. Pulando download.")
            return csv_path

        url = f"{RFB_BASE_URL}{filename}.zip"
        logger.info(f"  ⬇️ Baixando {url}...")

        try:
            response = requests.get(url, stream=True, timeout=600)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (50 * 1024 * 1024) == 0:
                        pct = (downloaded / total_size) * 100
                        logger.info(f"    Progress: {pct:.1f}%")

            # Extract
            logger.info(f"  📦 Extraindo {zip_path}...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(self.data_dir)
            os.remove(zip_path)
            return csv_path
        except Exception as e:
            logger.error(f"  ❌ Falha: {e}")
            return None

    # ── CSV Parsing (Streaming) ─────────────────────────────────────
    def parse_qsa_line(self, line: str) -> dict:
        """Public wrapper for parsing a single QSA line."""
        parts = line.split(";")
        return {
            "cnpj_basico": parts[0].strip().strip('"') if len(parts) > 0 else "",
            "identificador_socio": parts[1].strip().strip('"') if len(parts) > 1 else "",
            "nome_socio": parts[2].strip().strip('"') if len(parts) > 2 else "UNKNOWN",
            "cnpj_cpf_socio": parts[3].strip().strip('"') if len(parts) > 3 else "",
            "qualificacao_socio": parts[4].strip().strip('"') if len(parts) > 4 else "",
            "data_entrada": parts[5].strip().strip('"') if len(parts) > 5 else "",
        }

    def stream_socios_csv(self, csv_path: str) -> Generator[dict, None, None]:
        """
        Streaming generator: lê o CSV de sócios linha a linha.
        Sem carregar tudo na memória.
        """
        encodings = ['latin-1', 'utf-8', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    for line_num, line in enumerate(f):
                        line = line.strip()
                        if not line or line_num == 0:
                            continue
                        
                        try:
                            parsed = self.parse_qsa_line(line)
                            if parsed["cnpj_basico"] and parsed["nome_socio"]:
                                yield parsed
                        except Exception:
                            continue
                return  # Successfully read with this encoding
            except UnicodeDecodeError:
                continue

    def stream_empresas_csv(self, csv_path: str) -> Generator[dict, None, None]:
        """
        Streaming generator: lê o CSV de empresas linha a linha.
        """
        encodings = ['latin-1', 'utf-8', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    for line_num, line in enumerate(f):
                        line = line.strip()
                        if not line or line_num == 0:
                            continue
                        
                        parts = line.split(";")
                        try:
                            yield {
                                "cnpj_basico": parts[0].strip().strip('"'),
                                "razao_social": parts[1].strip().strip('"') if len(parts) > 1 else "",
                                "natureza_juridica": parts[2].strip().strip('"') if len(parts) > 2 else "",
                                "capital_social": parts[4].strip().strip('"').replace(",", ".") if len(parts) > 4 else "0",
                                "porte": parts[5].strip().strip('"') if len(parts) > 5 else ""
                            }
                        except Exception:
                            continue
                return
            except UnicodeDecodeError:
                continue

    # ── Neo4j Batch Ingestion ───────────────────────────────────────
    def ingest_qsa_to_neo4j(self, session, records: list):
        """
        Insere batch de registros QSA no Neo4j.
        Cria: (Pessoa)-[:SOCIO_ADMINISTRADOR_DE]->(Empresa)
        """
        query = """
        UNWIND $batch AS row
        MERGE (e:Empresa {cnpj: row.cnpj_basico})
        MERGE (p:Pessoa {name: row.nome_socio})
          ON CREATE SET p.cpf = row.cnpj_cpf_socio
        MERGE (p)-[:SOCIO_ADMINISTRADOR_DE {
            qualificacao: row.qualificacao_socio,
            data_entrada: row.data_entrada
        }]->(e)
        """
        session.run(query, batch=records)

    def ingest_empresas_to_neo4j(self, session, records: list):
        """
        Insere batch de empresas no Neo4j.
        """
        query = """
        UNWIND $batch AS row
        MERGE (e:Empresa {cnpj: row.cnpj_basico})
          ON CREATE SET e.name = row.razao_social,
                        e.natureza_juridica = row.natureza_juridica,
                        e.capital_social = toFloat(row.capital_social),
                        e.porte = row.porte
        """
        session.run(query, batch=records)

    def process_partition(self, file_type: str, partition: int, session=None):
        """
        Processa uma partição completa (download + parse + ingest).
        """
        csv_path = self.download_partition(file_type, partition)
        if not csv_path or not os.path.exists(csv_path):
            logger.error(f"  Arquivo não encontrado: {csv_path}")
            return

        target_session = session or self.neo4j_session
        if not target_session:
            logger.error("  Neo4j session não disponível!")
            return

        logger.info(f"  🔄 Processando {file_type}{partition}...")
        batch = []
        total_ingested = 0
        start_time = time.time()

        if file_type == "Socios":
            stream = self.stream_socios_csv(csv_path)
            ingest_fn = self.ingest_qsa_to_neo4j
        elif file_type == "Empresas":
            stream = self.stream_empresas_csv(csv_path)
            ingest_fn = self.ingest_empresas_to_neo4j
        else:
            logger.error(f"  Tipo de arquivo não suportado: {file_type}")
            return

        for record in stream:
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                ingest_fn(target_session, batch)
                total_ingested += len(batch)
                elapsed = time.time() - start_time
                rate = total_ingested / elapsed if elapsed > 0 else 0
                logger.info(f"    Ingested {total_ingested:,} records ({rate:.0f} rec/s)")
                batch = []

        # Flush remaining
        if batch:
            ingest_fn(target_session, batch)
            total_ingested += len(batch)

        elapsed = time.time() - start_time
        logger.info(f"  ✅ {file_type}{partition}: {total_ingested:,} registros em {elapsed:.1f}s")

    def run_full_ingestion(self, session=None):
        """
        Executa a ingestão completa de todas as 10 partições de Sócios e Empresas.
        CUIDADO: operação pesada que pode levar horas dependendo da rede e do HW.
        """
        target_session = session or self.neo4j_session
        logger.info("=== RFB CNPJ Full Ingestion ===")
        
        # Empresas first (create nodes)
        for i in range(RFB_PARTITIONS):
            self.process_partition("Empresas", i, target_session)
        
        # Then Sócios (create relationships)
        for i in range(RFB_PARTITIONS):
            self.process_partition("Socios", i, target_session)
        
        logger.info("=== Ingestão completa! ===")


# Backward-compatible functions
def parse_qsa_line(line: str) -> dict:
    loader = RFBCNPJLoader()
    return loader.parse_qsa_line(line)


def ingest_qsa_to_neo4j(session, records: list):
    loader = RFBCNPJLoader()
    loader.ingest_qsa_to_neo4j(session, records)


if __name__ == "__main__":
    loader = RFBCNPJLoader()
    logger.info("=== Receita Federal - CNPJ Batch Loader ===")
    logger.info("  Para ingestão completa, use: loader.run_full_ingestion(neo4j_session)")
    logger.info("  As 10 partições de Sócios+Empresas serão processadas em streaming.")
