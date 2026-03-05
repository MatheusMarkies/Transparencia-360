"""
TSE - Tribunal Superior Eleitoral (Batch Loader)
Source: https://dadosabertos.tse.jus.br/

Ingestão de Dumps CSV:
  - Doadores de Campanha (receitas_candidatos_*.csv)
  - Declarações de Bens (bem_candidato_*.csv)
  
Foco: Cruzar doadores de campanha com assessores parlamentares.
Se o assessor doa % alta do salário para a campanha do chefe,
é um forte indício de rachadinha.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import csv
import logging
import io
import zipfile
import requests
import shutil
import time
from collections import defaultdict
from typing import Optional, Generator

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TSE Dump URLs (example pattern - actual URLs vary per year)
TSE_BASE_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele"

# Known download patterns
TSE_DOWNLOADS = {
    "receitas_2022": f"{TSE_BASE_URL}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip",
    "bens_2022": f"{TSE_BASE_URL}/bem_candidato/bem_candidato_2022.zip",
    "receitas_2018": f"{TSE_BASE_URL}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2018.zip",
    "bens_2018": f"{TSE_BASE_URL}/bem_candidato/bem_candidato_2018.zip",
}


class TSEBatchLoader:
    """
    Processa dumps CSV do TSE para:
    1. Extrair doadores de campanha e cruzar com folha de pagamento
    2. Rastrear evolução patrimonial de candidatos
    3. Alimentar Neo4j com relações Doador → Candidato
    """
    def __init__(self, data_dir: Optional[str] = None):
        """
        Inicializa o Loader. Se data_dir não for passado, ele usa o Path relativo
        para salvar na pasta 'data/doacoes' na raiz do projeto Transparencia-360.
        """
        if data_dir is None:
            self.data_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "doacoes")
        else:
            self.data_dir = data_dir
            
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"📂 Diretório de dados do TSE configurado para: {self.data_dir}")

    # ── Download & Extract ──────────────────────────────────────────
    def download_dump(self, key: str) -> Optional[str]:
        """
        Baixa o dump, consolida os CSVs estaduais num único ficheiro mestre,
        e apaga a pasta cheia de arquivos residuais para poupar espaço.
        """
        url = TSE_DOWNLOADS.get(key)
        if not url: return None

        # O nosso arquivo final, limpo e consolidado
        consolidated_csv = os.path.join(self.data_dir, f"{key}_consolidado.csv")

        # 1. VALIDAÇÃO DO CACHE LIMPO
        if os.path.exists(consolidated_csv):
            logger.info(f"  ✅ Cache validado: Ficheiro mestre '{key}_consolidado.csv' já existe. Pulando download.")
            return consolidated_csv

        zip_path = os.path.join(self.data_dir, f"{key}.zip")
        extract_dir = os.path.join(self.data_dir, f"temp_{key}")

        logger.info(f"  ⬇️ Baixando dump TSE: {key}...")
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"  📦 Extraindo {zip_path}...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)
            os.remove(zip_path) # Apaga o ZIP pesado
            
            # --- OTIMIZAÇÃO: CONSOLIDAÇÃO E LIMPEZA DA VISTA ---
            logger.info("  🧹 Consolidando ficheiros para limpar a pasta...")
            all_csvs = list(Path(extract_dir).rglob("*.csv"))
            
            # Filtra apenas as receitas de candidatos (ignora partidos)
            target_csvs = [f for f in all_csvs if "receitas_candidatos" in f.name.lower() and "originario" not in f.name.lower()]
            
            if not target_csvs:
                target_csvs = all_csvs # Fallback
                
            # Procura se o TSE enviou o arquivo "BRASIL" (que já tem todos os estados)
            brasil_file = next((f for f in target_csvs if "BRASIL" in f.name.upper()), None)
            
            if brasil_file:
                logger.info("    Ficheiro 'BRASIL' detetado! Movendo e descartando ficheiros estaduais duplicados...")
                shutil.move(str(brasil_file), consolidated_csv)
            else:
                logger.info("    Juntando ficheiros estaduais num ficheiro único...")
                with open(consolidated_csv, 'w', encoding='utf-8') as out_f:
                    header_written = False
                    for csv_file in target_csvs:
                        for enc in ['latin-1', 'utf-8', 'cp1252']:
                            try:
                                with open(csv_file, 'r', encoding=enc) as in_f:
                                    lines = in_f.readlines()
                                    if not lines: break
                                    if not header_written:
                                        out_f.write(lines[0])
                                        header_written = True
                                    out_f.writelines(lines[1:])
                                break
                            except UnicodeDecodeError: continue
            
            # A MÁGICA: Apaga a pasta temporária cheia de lixo
            shutil.rmtree(extract_dir)
            logger.info(f"  ✨ Limpeza concluída! Criado ficheiro único: {consolidated_csv}")
            
            return consolidated_csv
            
        except Exception as e:
            logger.error(f"  ❌ Falha: {e}")
            if os.path.exists(zip_path): os.remove(zip_path)
            if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
            return None

    # ── Doadores de Campanha ────────────────────────────────────────
    def parse_receitas_csv(self, csv_path: str, target_candidate: Optional[str] = None) -> Generator[dict, None, None]:
        encodings = ['latin-1', 'utf-8', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        nm_cand = row.get("NM_CANDIDATO", "")
                        sq_cand = row.get("SQ_CANDIDATO") or row.get("SQ_PRESTADOR_CONTAS", "")
                        cpf_doador = row.get("NR_CPF_CNPJ_DOADOR") or row.get("NR_CPF_CNPJ_DOADOR_ORIGINARIO", "")
                        nm_doador = row.get("NM_DOADOR") or row.get("NM_DOADOR_ORIGINARIO", "")
                        valor_str = row.get("VR_RECEITA", "0")
                        fonte = row.get("DS_FONTE_RECEITA") or row.get("DS_RECEITA", "")
                        tipo = row.get("DS_ORIGEM_RECEITA", "")

                        if not nm_cand: continue

                        if target_candidate and target_candidate.upper() not in nm_cand.upper():
                            continue
                        
                        donation = {
                            "candidato": nm_cand,
                            "sq_candidato": sq_cand,
                            "cpf_cnpj_doador": cpf_doador,
                            "nome_doador": nm_doador,
                            "valor": self._safe_float(valor_str),
                            "fonte": fonte,
                            "tipo_receita": tipo
                        }
                        
                        if donation["valor"] > 0 and donation["cpf_cnpj_doador"]:
                            # 🚀 YIELD entrega uma linha de cada vez ao loop principal!
                            yield donation
                break
            except (UnicodeDecodeError, KeyError):
                continue

    # ── Declaração de Bens ──────────────────────────────────────────
    def parse_bens_csv(self, csv_path: str, target_candidate: Optional[str] = None) -> list[dict]:
        """
        Parseia o CSV de declaração de bens do TSE.
        
        Colunas:
        - NM_CANDIDATO, SQ_CANDIDATO
        - DS_TIPO_BEM_CANDIDATO
        - DS_BEM_CANDIDATO  (descrição)
        - VR_BEM_CANDIDATO  (valor declarado)
        """
        bens = []
        encodings = ['latin-1', 'utf-8', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        if target_candidate:
                            if target_candidate.upper() not in row.get("NM_CANDIDATO", "").upper():
                                continue
                        
                        bem = {
                            "candidato": row.get("NM_CANDIDATO", ""),
                            "tipo_bem": row.get("DS_TIPO_BEM_CANDIDATO", ""),
                            "descricao": row.get("DS_BEM_CANDIDATO", ""),
                            "valor": self._safe_float(row.get("VR_BEM_CANDIDATO", "0"))
                        }
                        bens.append(bem)
                break
            except (UnicodeDecodeError, KeyError):
                continue
        
        logger.info(f"  🏦 Parsed {len(bens)} declarações de bens")
        return bens

    # ── Rachadinha Cross-Check ──────────────────────────────────────
    def cross_check_donors_with_staff(
        self,
        donations: list[dict],
        staff_cpfs: list[str]
    ) -> list[dict]:
        """
        Cruza a lista de doadores de campanha com os CPFs dos assessores.
        Se um assessor (CPF da folha de pagamento) aparece como doador,
        é um forte indicador de rachadinha.
        
        Returns:
            Lista de matches com {nome_doador, cpf, valor_doado, candidato}
        """
        staff_set = set(cpf.replace(".", "").replace("-", "") for cpf in staff_cpfs)
        matches = []
        
        for d in donations:
            donor_cpf = d["cpf_cnpj_doador"].replace(".", "").replace("-", "")
            if donor_cpf in staff_set:
                matches.append({
                    "nome_doador": d["nome_doador"],
                    "cpf": d["cpf_cnpj_doador"],
                    "valor_doado": d["valor"],
                    "candidato": d["candidato"],
                    "fonte": d["fonte"]
                })
        
        if matches:
            logger.warning(f"  🚨 RACHADINHA ALERT: {len(matches)} assessores doaram para a campanha!")
            for m in matches:
                logger.warning(f"      → {m['nome_doador']}: R${m['valor_doado']:,.2f}")
        else:
            logger.info("  ✅ Nenhum assessor encontrado como doador de campanha.")
        
        return matches

    # ── Neo4j Ingestion ─────────────────────────────────────────────
    def ingest_donations_to_neo4j(self, session, batch: list[dict]):
        """
        Insere doações de campanha no grafo Neo4j.
        Cria relações: (Pessoa)-[:DOOU_PARA_CAMPANHA]->(Politico)
        """
        query = """
        UNWIND $batch AS row
        MERGE (doador:Pessoa {cpf: row.cpf_cnpj_doador})
          ON CREATE SET doador.name = row.nome_doador
        MERGE (cand:Politico {name: row.candidato})
        MERGE (doador)-[:DOOU_PARA_CAMPANHA {
            valor: row.valor,
            fonte: row.fonte,
            tipo: row.tipo_receita
        }]->(cand)
        """
        # Executa as 2000 linhas do batch de uma só vez
        session.run(query, batch=batch)

    # ── Helpers ──────────────────────────────────────────────────────
    def _safe_float(self, value: str) -> float:
        try:
            return float(value.replace(",", "."))
        except (ValueError, AttributeError):
            return 0.0

    def run_donation_ingestion(self, neo4j_uri: str, neo4j_user: str, neo4j_pass: str, target_year: str = "2022"):
        logger.info(f"=== Iniciando Ingestão de Doações ({target_year}) ===")
        
        key = f"receitas_{target_year}"
        consolidated_csv_path = self.download_dump(key)
        
        if not consolidated_csv_path or not os.path.exists(consolidated_csv_path):
            logger.error("Falha ao preparar os dados do TSE.")
            return

        logger.info("🔌 Conectando ao Neo4j...")
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))

        try:
            with driver.session() as session:
                # 🚀 O SEGREDO DA PERFORMANCE: Criar Índices B-Tree antes do MERGE
                logger.info("⚡ Criando Índices de Performance no Neo4j...")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pessoa) REQUIRE p.cpf IS UNIQUE")
                session.run("CREATE INDEX IF NOT EXISTS FOR (pol:Politico) ON (pol.name)")

                logger.info(f"📂 Processando {os.path.basename(consolidated_csv_path)} em STREAMING...")
                
                batch = []
                total_ingested = 0
                start_time = time.time()
                
                # Consome o generator linha a linha (RAM quase zero)
                for d in self.parse_receitas_csv(consolidated_csv_path):
                    # Limpa a pontuação do CPF
                    d["cpf_cnpj_doador"] = d["cpf_cnpj_doador"].replace(".", "").replace("-", "").replace("/", "")
                    batch.append(d)
                    
                    # 🚀 Dispara para o banco de 2000 em 2000 (Sweet spot do Neo4j)
                    if len(batch) >= 2000:
                        self.ingest_donations_to_neo4j(session, batch)
                        total_ingested += len(batch)
                        batch = []
                        if total_ingested % 20000 == 0:
                            logger.info(f"    ⏳ Já inseridos {total_ingested:,} registos... ({(time.time()-start_time):.1f}s)")
                
                # Descarrega o resto que sobrou
                if batch:
                    self.ingest_donations_to_neo4j(session, batch)
                    total_ingested += len(batch)
                    
                elapsed = time.time() - start_time
                rate = total_ingested / elapsed if elapsed > 0 else 0
                logger.info(f"🎉 SUCESSO! {total_ingested:,} doações inseridas em {elapsed:.1f}s ({rate:.0f} linhas/segundo)")
                        
        except Exception as e:
            logger.error(f"Erro durante a ingestão: {e}")
        finally:
            driver.close()
            logger.info("✅ Conexão com Neo4j encerrada.")

if __name__ == "__main__":
    loader = TSEBatchLoader()
    
    # Credenciais do seu Neo4j (ajuste conforme seu docker-compose / .env)
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password") # Coloque a senha correta aqui
    
    # Executa a ingestão para as eleições de 2022
    loader.run_donation_ingestion(NEO4J_URI, NEO4J_USER, NEO4J_PASS, target_year="2022")
