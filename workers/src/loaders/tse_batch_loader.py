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
from collections import defaultdict
from typing import Optional

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
    def __init__(self, data_dir: str = "/tmp/tse_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    # ── Download & Extract ──────────────────────────────────────────
    def download_dump(self, key: str) -> Optional[str]:
        """
        Baixa um dump ZIP do TSE e extrai na pasta data_dir.
        Retorna o caminho da pasta extraída.
        """
        url = TSE_DOWNLOADS.get(key)
        if not url:
            logger.error(f"Chave de download desconhecida: {key}")
            return None

        zip_path = os.path.join(self.data_dir, f"{key}.zip")
        extract_dir = os.path.join(self.data_dir, key)

        if os.path.exists(extract_dir):
            logger.info(f"  ✅ Dump '{key}' já existente, pulando download.")
            return extract_dir

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
            os.remove(zip_path)
            return extract_dir
        except Exception as e:
            logger.error(f"  ❌ Falha ao baixar/extrair {key}: {e}")
            return None

    # ── Doadores de Campanha ────────────────────────────────────────
    def parse_receitas_csv(self, csv_path: str, target_candidate: Optional[str] = None) -> list[dict]:
        """
        Parseia o CSV de receitas de campanha do TSE.
        
        Colunas relevantes no CSV (pode variar por ano):
        - NM_CANDIDATO / SQ_CANDIDATO
        - NR_CPF_CNPJ_DOADOR
        - NM_DOADOR
        - VR_RECEITA (valor da doação)
        - DS_FONTE_RECEITA
        """
        donations = []
        encodings = ['latin-1', 'utf-8', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        # Filter by candidate if specified
                        if target_candidate:
                            candidate_name = row.get("NM_CANDIDATO", "")
                            if target_candidate.upper() not in candidate_name.upper():
                                continue
                        
                        donation = {
                            "candidato": row.get("NM_CANDIDATO", ""),
                            "sq_candidato": row.get("SQ_CANDIDATO", ""),
                            "cpf_cnpj_doador": row.get("NR_CPF_CNPJ_DOADOR", ""),
                            "nome_doador": row.get("NM_DOADOR", ""),
                            "valor": self._safe_float(row.get("VR_RECEITA", "0")),
                            "fonte": row.get("DS_FONTE_RECEITA", ""),
                            "tipo_receita": row.get("DS_ORIGEM_RECEITA", "")
                        }
                        if donation["valor"] > 0:
                            donations.append(donation)
                break
            except (UnicodeDecodeError, KeyError):
                continue
        
        logger.info(f"  📊 Parsed {len(donations)} doações de campanha")
        return donations

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
    def ingest_donations_to_neo4j(self, session, donations: list[dict]):
        """
        Insere doações de campanha no grafo Neo4j.
        Cria relações: (Pessoa)-[:DOOU_PARA_CAMPANHA]->(Politico)
        """
        query = """
        UNWIND $batch AS row
        MERGE (doador:Pessoa {cpf: row.cpf_cnpj_doador, name: row.nome_doador})
        MERGE (cand:Politico {name: row.candidato})
        MERGE (doador)-[:DOOU_PARA_CAMPANHA {
            valor: row.valor,
            fonte: row.fonte,
            tipo: row.tipo_receita
        }]->(cand)
        """
        # Batch in chunks of 500
        for i in range(0, len(donations), 500):
            chunk = donations[i:i+500]
            session.run(query, batch=chunk)
            logger.info(f"  Ingested batch {i//500 + 1} ({len(chunk)} doações)")

    # ── Helpers ──────────────────────────────────────────────────────
    def _safe_float(self, value: str) -> float:
        try:
            return float(value.replace(",", "."))
        except (ValueError, AttributeError):
            return 0.0


if __name__ == "__main__":
    loader = TSEBatchLoader()
    logger.info("=== TSE Batch Loader ===")
    
    # Download all available dumps
    for key in TSE_DOWNLOADS:
        result = loader.download_dump(key)
        if result:
            logger.info(f"  Dados disponíveis em: {result}")
