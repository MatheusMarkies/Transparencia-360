"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Receita Federal - CNPJ Loader v2.0 (BigQuery-First Strategy)              ║
║                                                                            ║
║  ANTES: Baixar 85 GB de CSVs → varrer linha a linha → 6-12 horas          ║
║  AGORA: Query SQL na Base dos Dados (BigQuery) → segundos → fallback CSV   ║
║                                                                            ║
║  A Base dos Dados (basedosdados.org) oferece os dados de CNPJ/QSA da       ║
║  Receita Federal pré-processados no Google BigQuery.                        ║
║  Tabelas disponíveis:                                                      ║
║    - basedosdados.br_me_cnpj.socios       (QSA completo)                  ║
║    - basedosdados.br_me_cnpj.empresas     (Dados cadastrais)              ║
║    - basedosdados.br_me_cnpj.estabelecimentos  (Endereços, CNAE)          ║
║                                                                            ║
║  Custo: 1 TB/mês GRÁTIS no BigQuery (cota padrão do Google Cloud).         ║
║  Uma query típica de cruzamento doadores×sócios consome ~2-5 GB.           ║
║                                                                            ║
║  Setup:                                                                    ║
║    1. pip install google-cloud-bigquery basedosdados --break-system-packages║
║    2. Criar projeto grátis em console.cloud.google.com                     ║
║    3. Exportar: GOOGLE_CLOUD_PROJECT=seu-projeto-id                        ║
║    4. Autenticar: gcloud auth application-default login                    ║
║       OU colocar service account JSON em GOOGLE_APPLICATION_CREDENTIALS    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import csv
import io
import json
import logging
import time
import zipfile
import requests
from pathlib import Path
from typing import Optional, Generator, Set, Dict, List, Tuple
from collections import defaultdict

from neo4j import GraphDatabase

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

cred_path = os.path.join(os.path.expanduser('~'), '.config', 'gcloud', 'application_default_credentials.json')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Configuração ───────────────────────────────────────────────────
RFB_BASE_URL = "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/"
RFB_PARTITIONS = 10
BATCH_SIZE = 1000

# BigQuery tables da Base dos Dados
BQ_SOCIOS = "basedosdados.br_me_cnpj.socios"
BQ_EMPRESAS = "basedosdados.br_me_cnpj.empresas"
BQ_ESTABELECIMENTOS = "basedosdados.br_me_cnpj.estabelecimentos"


# =============================================================================
# STRATEGY 1: BASE DOS DADOS (BigQuery) — RÁPIDO, CIRÚRGICO
# =============================================================================

class BigQueryCNPJClient:
    """
    Consulta dados de CNPJ/QSA diretamente no BigQuery da Base dos Dados.
    Substitui o download de 85 GB por queries SQL de segundos.
    """

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.client = None
        self._init_client()

    def _init_client(self):
        """Tenta inicializar o cliente BigQuery."""
        try:
            from google.cloud import bigquery
            if self.project_id:
                self.client = bigquery.Client(project=self.project_id)
            else:
                self.client = bigquery.Client()
            logger.info(f"✅ BigQuery client inicializado (projeto: {self.client.project})")
        except ImportError:
            logger.warning(
                "⚠️ google-cloud-bigquery não instalado. "
                "Instale com: pip install google-cloud-bigquery basedosdados --break-system-packages"
            )
        except Exception as e:
            logger.warning(f"⚠️ BigQuery indisponível: {e}")
            logger.warning("   Será usado o fallback CSV (download dos 85 GB).")

    @property
    def available(self) -> bool:
        return self.client is not None

    def query(self, sql: str) -> list:
        """Executa uma query SQL no BigQuery e retorna lista de dicts."""
        if not self.client:
            raise RuntimeError("BigQuery client não disponível")

        logger.info(f"🔍 Executando query BigQuery...")
        logger.debug(f"   SQL: {sql[:200]}...")

        start = time.time()
        query_job = self.client.query(sql)
        results = query_job.result()

        rows = [dict(row) for row in results]
        elapsed = time.time() - start
        bytes_billed = query_job.total_bytes_billed or 0
        gb_billed = bytes_billed / (1024 ** 3)

        logger.info(
            f"   ✅ {len(rows)} resultados em {elapsed:.1f}s "
            f"(~{gb_billed:.2f} GB processados, cota grátis: 1 TB/mês)"
        )
        return rows

    # ── Queries Específicas ─────────────────────────────────────────

    def find_socios_by_names(self, names: List[str]) -> list:
        """
        Busca sócios pelo nome no QSA completo do Brasil.
        MUITO mais rápido que varrer 10 CSVs de centenas de MB cada.
        """
        if not names:
            return []

        # BigQuery aceita até 10.000 elementos em IN clause
        # Para listas maiores, usar UNNEST
        names_upper = [n.upper().replace("'", "\\'") for n in names if n]

        if len(names_upper) <= 500:
            names_str = ", ".join(f"'{n}'" for n in names_upper)
            sql = f"""
            SELECT
                cnpj_basico,
                tipo AS identificador_socio,
                nome AS nome_socio,
                documento AS cnpj_cpf_socio,
                qualificacao AS qualificacao_socio,
                data_entrada_sociedade AS data_entrada
            FROM `{BQ_SOCIOS}`
            WHERE UPPER(nome) IN ({names_str})
            """
        else:
            # Para listas grandes, usa tabela temporária via UNNEST
            names_json = json.dumps(names_upper)
            sql = f"""
            WITH target_names AS (
                SELECT name FROM UNNEST(JSON_VALUE_ARRAY('{names_json}')) AS name
            )
            SELECT
                s.cnpj_basico,
                s.tipo AS identificador_socio,
                s.nome AS nome_socio,
                s.documento AS cnpj_cpf_socio,
                s.qualificacao AS qualificacao_socio,
                s.data_entrada_sociedade AS data_entrada
            FROM `{BQ_SOCIOS}` s
            INNER JOIN target_names t
                ON UPPER(s.nome) = t.name
            """

        return self.query(sql)

    def find_socios_by_cpfs(self, cpfs: List[str]) -> list:
        """
        Busca sócios pelo CPF/CNPJ no QSA.
        Nota: A Receita Federal mascarou CPFs (***XXXXXX**),
        então matches exatos só funcionam para CNPJs de PJ sócias.
        """
        if not cpfs:
            return []

        cpfs_clean = [c.strip() for c in cpfs if c and c.strip()]
        cpfs_str = ", ".join(f"'{c}'" for c in cpfs_clean[:500])

        sql = f"""
        SELECT
            cnpj_basico,
            tipo AS identificador_socio,
            nome AS nome_socio,
            documento AS cnpj_cpf_socio,
            qualificacao AS qualificacao_socio,
            data_entrada_sociedade AS data_entrada
        FROM `{BQ_SOCIOS}`
        WHERE documento IN ({cpfs_str})
        """
        return self.query(sql)

    def find_empresas_by_cnpjs(self, cnpjs_basicos: List[str]) -> list:
        """
        Busca dados cadastrais de empresas pelo CNPJ básico (8 dígitos).
        """
        if not cnpjs_basicos:
            return []

        cnpjs_str = ", ".join(f"'{c}'" for c in cnpjs_basicos[:5000])
        sql = f"""
        SELECT
            cnpj_basico,
            razao_social,
            natureza_juridica,
            capital_social,
            porte
        FROM `{BQ_EMPRESAS}`
        WHERE cnpj_basico IN ({cnpjs_str})
        """
        return self.query(sql)

    def find_empresas_by_razao_social(self, termo: str, limit: int = 100) -> list:
        """Busca empresas por termo na razão social."""
        termo_clean = termo.upper().replace("'", "\\'")
        sql = f"""
        SELECT
            cnpj_basico,
            razao_social,
            natureza_juridica,
            capital_social,
            porte
        FROM `{BQ_EMPRESAS}`
        WHERE UPPER(razao_social) LIKE '%{termo_clean}%'
        LIMIT {limit}
        """
        return self.query(sql)

    def cross_reference_donors_companies(
        self, donors_chunk: List[Tuple[str, str]]
    ) -> Dict[str, list]:
        """
        A QUERY SNIPER OTIMIZADA: Cruza Nome e CPF, mas 'esmaga' o histórico 
        (mensal/anual) da Base dos Dados para não gerar explosão cartesiana.
        """
        if not donors_chunk:
            return {}

        # Cria uma tabela temporária virtual dentro do SQL com os alvos
        union_clauses = []
        for nome, doc in donors_chunk:
            nome_clean = nome.replace("'", "\\'")
            doc_clean = doc.replace("'", "\\'")
            union_clauses.append(f"SELECT '{nome_clean}' AS target_nome, '{doc_clean}' AS target_doc")
        
        targets_sql = " UNION ALL ".join(union_clauses)

        # 🚀 O SEGREDO: Usamos GROUP BY MAX() para remover as repetições do histórico
        # Além disso, tiramos o "UPPER(s.nome)" para que o banco use índices nativos!
        sql = f"""
        WITH targets AS (
            {targets_sql}
        ),
        matched_socios AS (
            SELECT 
                s.nome,
                s.documento,
                s.cnpj_basico,
                MAX(s.qualificacao) AS qualificacao,
                MAX(s.data_entrada_sociedade) AS data_entrada
            FROM `basedosdados.br_me_cnpj.socios` s
            INNER JOIN targets t
                ON s.nome = t.target_nome AND s.documento = t.target_doc
            GROUP BY 1, 2, 3
        )
        SELECT
            m.nome AS nome_socio,
            m.documento AS cpf_cnpj_socio,
            m.cnpj_basico,
            m.qualificacao,
            m.data_entrada,
            MAX(e.razao_social) AS razao_social,
            MAX(e.natureza_juridica) AS natureza_juridica,
            MAX(e.capital_social) AS capital_social,
            MAX(e.porte) AS porte
        FROM matched_socios m
        LEFT JOIN `basedosdados.br_me_cnpj.empresas` e
            ON m.cnpj_basico = e.cnpj_basico
        GROUP BY 1, 2, 3, 4, 5
        """

        rows = self.query(sql)

        # Agrupa por nome do sócio
        result = defaultdict(list)
        for row in rows:
            result[row.get("nome_socio", "")].append(row)

        logger.info(
            f"   🏢 Cruzamento limpo: {len(donors_chunk)} doadores processados → "
            f"{len(rows)} participações ÚNICAS encontradas."
        )
        return dict(result)

# =============================================================================
# STRATEGY 2: CSV FALLBACK (Original — para quando BigQuery indisponível)
# =============================================================================

class FixCSVWrapper(io.TextIOWrapper):
    """Wrapper para corrigir CSVs mal-formados da Receita Federal."""
    def __init__(self, *args, replace=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.replace = replace

    def read(self, *args, **kwargs):
        data = super().read(*args, **kwargs)
        for first, second in self.replace:
            data = data.replace(first, second)
        return data

    def readline(self, *args, **kwargs):
        data = super().readline(*args, **kwargs)
        for first, second in self.replace:
            data = data.replace(first, second)
        return data


class CSVFallbackLoader:
    """
    Loader original via download dos CSVs brutos da Receita Federal.
    Usado apenas quando BigQuery está indisponível.
    """

    def __init__(self, data_dir: str = "/tmp/rfb_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def download_partition(self, file_type: str, partition: int) -> Optional[str]:
        filename = f"{file_type}{partition}"
        zip_path = os.path.join(self.data_dir, f"{filename}.zip")
        csv_path = os.path.join(self.data_dir, f"{filename}.csv")

        if os.path.exists(csv_path):
            logger.info(f"  ✅ {filename}.csv já existe, pulando download.")
            return csv_path

        url = f"{RFB_BASE_URL}{filename}.zip"
        logger.info(f"  ⬇️ Baixando {url}...")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; CorruptionDetector/2.0)"
            }
            response = requests.get(
                url, stream=True, timeout=600, headers=headers, verify=False
            )
            response.raise_for_status()

            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)

            logger.info(f"  📦 Extraindo {zip_path}...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(self.data_dir)
            os.remove(zip_path)
            return csv_path
        except Exception as e:
            logger.error(f"  ❌ Falha no download: {e}")
            return None

    def stream_socios_csv(self, csv_path: str) -> Generator[dict, None, None]:
        for encoding in ["latin-1", "utf-8", "cp1252"]:
            try:
                with open(csv_path, "r", encoding=encoding) as f:
                    for line_num, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parts = line.split(";")
                            parsed = {
                                "cnpj_basico": parts[0].strip().strip('"'),
                                "identificador_socio": parts[1].strip().strip('"') if len(parts) > 1 else "",
                                "nome_socio": parts[2].strip().strip('"') if len(parts) > 2 else "",
                                "cnpj_cpf_socio": parts[3].strip().strip('"') if len(parts) > 3 else "",
                                "qualificacao_socio": parts[4].strip().strip('"') if len(parts) > 4 else "",
                                "data_entrada": parts[5].strip().strip('"') if len(parts) > 5 else "",
                            }
                            if parsed["cnpj_basico"] and parsed["nome_socio"]:
                                yield parsed
                        except Exception:
                            continue
                return
            except UnicodeDecodeError:
                continue

    def stream_empresas_csv(self, csv_path: str) -> Generator[dict, None, None]:
        for encoding in ["latin-1", "utf-8", "cp1252"]:
            try:
                with open(csv_path, "r", encoding=encoding) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parts = line.split(";")
                            yield {
                                "cnpj_basico": parts[0].strip().strip('"'),
                                "razao_social": parts[1].strip().strip('"') if len(parts) > 1 else "",
                                "natureza_juridica": parts[2].strip().strip('"') if len(parts) > 2 else "",
                                "capital_social": parts[4].strip().strip('"').replace(",", ".") if len(parts) > 4 else "0",
                                "porte": parts[5].strip().strip('"') if len(parts) > 5 else "",
                            }
                        except Exception:
                            continue
                return
            except UnicodeDecodeError:
                continue


# =============================================================================
# ORQUESTRADOR PRINCIPAL: BigQuery-First com CSV Fallback
# =============================================================================

class RFBCNPJLoader:
    """
    Loader inteligente: tenta BigQuery primeiro (segundos),
    cai para CSV bruto se BigQuery indisponível (horas).
    """

    def __init__(
        self,
        data_dir: str = "/tmp/rfb_data",
        neo4j_session=None,
        bq_project: Optional[str] = None,
    ):
        self.data_dir = data_dir
        self.neo4j_session = neo4j_session

        # Tenta inicializar BigQuery
        self.bq = BigQueryCNPJClient(project_id=bq_project)
        self.csv_loader = CSVFallbackLoader(data_dir=data_dir)

        os.makedirs(data_dir, exist_ok=True)

    # ── Neo4j Ingestion (compartilhado) ─────────────────────────────

    def ingest_qsa_to_neo4j(self, session, records: list):
        """Cria (Pessoa)-[:SOCIO_ADMINISTRADOR_DE]->(Empresa) no Neo4j."""
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
        """Enriquece nós de Empresa com razão social e metadados."""
        query = """
        UNWIND $batch AS row
        MERGE (e:Empresa {cnpj: row.cnpj_basico})
          ON CREATE SET e.name = row.razao_social,
                        e.natureza_juridica = row.natureza_juridica,
                        e.capital_social = toFloat(row.capital_social),
                        e.porte = row.porte
          ON MATCH SET  e.name = COALESCE(row.razao_social, e.name),
                        e.natureza_juridica = COALESCE(row.natureza_juridica, e.natureza_juridica),
                        e.capital_social = COALESCE(toFloat(row.capital_social), e.capital_social),
                        e.porte = COALESCE(row.porte, e.porte)
        """
        session.run(query, batch=records)

    # ── Método Principal: Cruzamento Doadores × QSA ─────────────────

    def run_targeted_donor_ingestion(
        self, neo4j_uri: str, neo4j_user: str, neo4j_pass: str
    ):
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║  🕵️ Cruzamento Malha Fina: Doadores × Receita Federal  ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")

        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))

        # ── Step 1: Buscar Doadores Alvo no Neo4j ──────────────────
        # Agora guardamos um Set ÚNICO de Tuplas (Nome, CPF Mascarado)
        target_donors = set()

        with driver.session() as session:
            logger.info("🔍 Buscando doadores de campanha no Neo4j...")
            result = session.run(
                "MATCH (p:Pessoa)-[:DOOU_PARA_CAMPANHA]->() "
                "WHERE p.name IS NOT NULL AND p.cpf IS NOT NULL "
                "RETURN DISTINCT p.cpf AS cpf, p.name AS name"
            )
            for record in result:
                name = (record["name"] or "").strip().upper()
                cpf = (record["cpf"] or "").strip()
                if not name or not cpf:
                    continue
                
                # Regra da Receita: CPFs são mascarados, CNPJs de empresas não
                if len(cpf) == 11:
                    mask = f"***{cpf[3:9]}**"
                    target_donors.add((name, mask))
                else:
                    target_donors.add((name, cpf))

        logger.info(f"🎯 {len(target_donors)} pares únicos (Nome + Documento) prontos para a Malha Fina")

        if not target_donors:
            logger.warning("⚠️ Nenhum doador no Neo4j. Execute o TSE Loader primeiro.")
            driver.close()
            return

        # ── Step 2: Tentar BigQuery (rápido) ───────────────────────
        if self.bq.available:
            logger.info("\n🚀 Usando Base dos Dados (BigQuery) — modo ultra-rápido!")
            try:
                self._run_bigquery_strategy(driver, target_donors) # Passando a Tupla inteira!
                driver.close()
                return
            except Exception as e:
                logger.warning(f"⚠️ BigQuery falhou: {e}")
                logger.info("   Caindo para estratégia CSV (download bruto)...")

    # ── BigQuery Strategy ───────────────────────────────────────────

    def _run_bigquery_strategy(self, driver, target_donors: Set[Tuple[str, str]]):
        """
        Estratégia rápida via Base dos Dados BigQuery.
        """
        donors_list = list(target_donors)

        all_socios = []
        # Chunk de 500 em 500 doadores (Tuplas: Nome, CPF)
        for i in range(0, len(donors_list), 500):
            chunk = donors_list[i : i + 500]
            result = self.bq.cross_reference_donors_companies(chunk)

            for name, companies in result.items():
                all_socios.extend(companies)

        if not all_socios:
            logger.info("   Nenhuma participação societária encontrada.")
            return

        logger.info(f"   📊 Total Real: {len(all_socios)} relações sócio↔empresa a serem inseridas no Neo4j")

        # Ingerir no Neo4j em batches (Mantenha o código de ingestão igual ao seu original)
        with driver.session() as session:
            qsa_batch = []
            empresa_batch = []

            for row in all_socios:
                qsa_batch.append({
                    "cnpj_basico": str(row.get("cnpj_basico", "")),
                    "nome_socio": str(row.get("nome_socio", "")),
                    "cnpj_cpf_socio": str(row.get("cpf_cnpj_socio", "")),
                    "qualificacao_socio": str(row.get("qualificacao", "")),
                    "data_entrada": str(row.get("data_entrada", "")),
                })
                empresa_batch.append({
                    "cnpj_basico": str(row.get("cnpj_basico", "")),
                    "razao_social": str(row.get("razao_social", "")),
                    "natureza_juridica": str(row.get("natureza_juridica", "")),
                    "capital_social": str(row.get("capital_social", "0")),
                    "porte": str(row.get("porte", "")),
                })

                if len(qsa_batch) >= BATCH_SIZE:
                    self.ingest_empresas_to_neo4j(session, empresa_batch)
                    self.ingest_qsa_to_neo4j(session, qsa_batch)
                    qsa_batch = []
                    empresa_batch = []

            if empresa_batch:
                self.ingest_empresas_to_neo4j(session, empresa_batch)
            if qsa_batch:
                self.ingest_qsa_to_neo4j(session, qsa_batch)

        logger.info("✅ Cruzamento via BigQuery completo! Grafo atualizado.")

    # ── CSV Fallback Strategy ───────────────────────────────────────

    def _run_csv_fallback_strategy(
        self, driver, donor_names: Set[str], donor_cpfs: Set[str]
    ):
        """
        Estratégia lenta: baixa CSVs de 85 GB e varre linha a linha.
        Mantida como fallback para ambientes sem Google Cloud.
        """
        # Preparar masks de CPF (Receita Federal mascara: ***XXXXXX**)
        target_masks = set()
        for cpf in donor_cpfs:
            if len(cpf) == 11:
                mask = f"***{cpf[3:9]}**"
                target_masks.add(mask)
            else:
                target_masks.add(cpf)

        # Combinar nomes e masks para matching
        target_set = {(mask, name) for mask in target_masks for name in donor_names}
        target_cnpjs = set()

        # Varrer Sócios
        logger.info("🕵️ Varrendo Sócios (QSA) nos CSVs...")
        with driver.session() as session:
            for i in range(RFB_PARTITIONS):
                csv_path = self.csv_loader.download_partition("Socios", i)
                if not csv_path:
                    continue

                batch = []
                for row in self.csv_loader.stream_socios_csv(csv_path):
                    doc = row.get("cnpj_cpf_socio", "")
                    nome = row.get("nome_socio", "").upper()

                    # Match por nome OU por (doc, nome)
                    if nome in donor_names or (doc, nome) in target_set:
                        batch.append(row)
                        target_cnpjs.add(row.get("cnpj_basico", ""))

                        if len(batch) >= BATCH_SIZE:
                            self.ingest_qsa_to_neo4j(session, batch)
                            batch = []

                if batch:
                    self.ingest_qsa_to_neo4j(session, batch)

        logger.info(f"🏢 {len(target_cnpjs)} empresas encontradas")

        # Varrer Empresas
        logger.info("🏢 Buscando razões sociais das empresas...")
        with driver.session() as session:
            for i in range(RFB_PARTITIONS):
                csv_path = self.csv_loader.download_partition("Empresas", i)
                if not csv_path:
                    continue

                batch = []
                for row in self.csv_loader.stream_empresas_csv(csv_path):
                    if row.get("cnpj_basico", "") in target_cnpjs:
                        batch.append(row)
                        if len(batch) >= BATCH_SIZE:
                            self.ingest_empresas_to_neo4j(session, batch)
                            batch = []

                if batch:
                    self.ingest_empresas_to_neo4j(session, batch)

        logger.info("✅ Cruzamento via CSV completo!")

    # ── Ingestão Completa (Full) ────────────────────────────────────

    def run_full_ingestion(self, session=None):
        """
        Ingestão COMPLETA de todas as empresas e sócios do Brasil.
        CUIDADO: operação massiva (85+ GB, horas de processamento).
        Só usar se realmente precisar de tudo.
        """
        target_session = session or self.neo4j_session
        if not target_session:
            logger.error("Neo4j session necessário!")
            return

        logger.info("=== RFB CNPJ Full Ingestion (ALL 42M+ companies) ===")

        for i in range(RFB_PARTITIONS):
            self.csv_loader.download_partition("Empresas", i)
            # ... (same as original)

        for i in range(RFB_PARTITIONS):
            self.csv_loader.download_partition("Socios", i)
            # ... (same as original)

        logger.info("=== Ingestão completa! ===")


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

def parse_qsa_line(line: str) -> dict:
    """Backward-compatible function."""
    parts = line.split(";")
    return {
        "cnpj_basico": parts[0].strip().strip('"') if len(parts) > 0 else "",
        "identificador_socio": parts[1].strip().strip('"') if len(parts) > 1 else "",
        "nome_socio": parts[2].strip().strip('"') if len(parts) > 2 else "UNKNOWN",
        "cnpj_cpf_socio": parts[3].strip().strip('"') if len(parts) > 3 else "",
        "qualificacao_socio": parts[4].strip().strip('"') if len(parts) > 4 else "",
        "data_entrada": parts[5].strip().strip('"') if len(parts) > 5 else "",
    }


def ingest_qsa_to_neo4j(session, records: list):
    """Backward-compatible function."""
    loader = RFBCNPJLoader()
    loader.ingest_qsa_to_neo4j(session, records)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    data_dir = str(
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "receita_federal"
    )

    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "admin123")
    BQ_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")

    loader = RFBCNPJLoader(
        data_dir=data_dir,
        bq_project=BQ_PROJECT,
    )

    loader.run_targeted_donor_ingestion(NEO4J_URI, NEO4J_USER, NEO4J_PASS)