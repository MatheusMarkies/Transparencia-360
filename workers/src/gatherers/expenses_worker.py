"""
Expenses Worker - Extracts real expense data from the Câmara dos Deputados.

Strategy: Uses the "Turicas Logic" to mass-download the yearly ZIP file,
fixes broken string patterns in memory, parses the CSV efficiently, and
pushes EVERY receipt to the backend to maintain a 360 view of the expenses.
OPTIMIZED: Skips massive downloads if the Parquet file already exists locally.
"""

import sys
import io
import csv
import zipfile
import requests
import argparse
from pathlib import Path
from collections import defaultdict
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import logging
from workers.src.core.api_client import GovAPIClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"

# ==============================================================================
# LÓGICA DO TURICAS PARA CORREÇÃO DE BUGS NOS CSVS DO GOVERNO
# ==============================================================================
class FixCSVWrapper(io.TextIOWrapper):
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


class ExpensesWorker:
    def __init__(self, year: int = 2025):
        self.api = GovAPIClient(CAMARA_API_BASE, request_delay=0.3)
        self.backend = BackendClient()
        self.year = year
        # Define o caminho do Parquet
        self.output_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"
        self.parquet_path = self.output_dir / f"ceap_{self.year}_raw.parquet"

    def _fetch_all_deputies(self) -> list:
        """Fetch all active deputy IDs and metadata from the modern API."""
        all_deputies = []
        page = 1
        while True:
            resp = self.api.get("deputados", params={"pagina": page, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"})
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            all_deputies.extend(resp["dados"])
            
            links = resp.get("links", [])
            has_next = any(l.get("rel") == "next" for l in links)
            if not has_next:
                break
            page += 1
        return all_deputies

    def _read_from_local_parquet(self, target_ids: set):
        """Lê os dados diretamente do Parquet local se ele já existir."""
        logger.info(f"📂 Encontrado arquivo local {self.parquet_path}. Pulando download do Governo...")
        df = pd.read_parquet(self.parquet_path)
        
        totals = defaultdict(float)
        receipts = defaultdict(list)
        
        for _, row in df.iterrows():
            dep_id_str = str(row.get('idecadastro', '')).split('.')[0] # Tira o .0 se for float
            if not dep_id_str.isdigit(): continue
            
            dep_id = int(dep_id_str)
            if dep_id not in target_ids: continue
            
            try:
                valor = float(row.get('vlrliquido', 0.0))
            except ValueError:
                valor = 0.0
            
            totals[dep_id] += valor
            
            categoria = str(row.get('txtdescricao', '')).strip().upper()
            data_doc = str(row.get('datemissao', ''))
            if data_doc and 'T' in data_doc: data_doc = data_doc.split('T')[0]
            elif data_doc and ' ' in data_doc: data_doc = data_doc.split(' ')[0]
            
            if data_doc and data_doc != 'nan' and data_doc != 'None':
                num_doc = str(row.get('numdocumento', 'unknown'))
                fornecedor = str(row.get('txtfornecedor', 'Unknown'))
                
                despesa_node = {
                    "id": f"despesa_{num_doc}_{abs(hash(fornecedor))}",
                    "dataEmissao": data_doc[:10],
                    "ufFornecedor": str(row.get('sguf', 'NA')),
                    "categoria": categoria,
                    "valorDocumento": valor,
                    "nomeFornecedor": fornecedor
                }
                receipts[dep_id].append(despesa_node)
                
        return totals, receipts


    def _mass_download_and_parse(self, target_ids: set):
        """Baixa o ZIP massivo do ano e extrai notas fiscais."""
        
        # === A GRANDE OTIMIZAÇÃO: VERIFICA SE EXISTE NO DISCO PRIMEIRO ===
        if self.parquet_path.exists():
            return self._read_from_local_parquet(target_ids)

        # Se não existe, vai buscar ao Governo
        url = f"https://www.camara.leg.br/cotas/Ano-{self.year}.csv.zip"
        logger.info(f"📥 Baixando pacote massivo do CEAP {self.year} (Logica Turicas)...")
        
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            logger.error(f"Erro ao baixar CSV: HTTP {response.status_code}")
            return {}, {}
            
        zip_file = zipfile.ZipFile(io.BytesIO(response.content))
        filename = zip_file.filelist[0].filename
        
        replace_rules = ()
        if self.year == 2011:
            replace_rules = ((';"SN;', ";SN;"),)
        elif self.year == 2018:
            replace_rules = ((';"LUPA', ";LUPA"), (';"EMBAIXADA', ";EMBAIXADA"))
            
        logger.info("🧹 Sanitizando e extraindo 100% das notas em memória...")
        fobj = FixCSVWrapper(zip_file.open(filename), encoding="utf-8-sig", replace=replace_rules)
        
        csv.field_size_limit(1024 ** 2)
        reader = csv.DictReader(fobj, delimiter=";")
        
        totals = defaultdict(float)
        receipts = defaultdict(list)
        
        raw_rows = []
        for row in reader:
            row = {k.lower(): v for k, v in row.items() if k}
            raw_rows.append(row) # Salva para o Parquet
            
            dep_id_str = row.get("idecadastro", "")
            if not dep_id_str.isdigit():
                continue
                
            dep_id = int(dep_id_str)
            if dep_id not in target_ids:
                continue
                
            try:
                valor = float(row.get("vlrliquido", "0").replace(",", "."))
            except ValueError:
                valor = 0.0
                
            totals[dep_id] += valor
            
            # Extrai 100% das categorias
            categoria = row.get("txtdescricao", "").strip().upper()
            data_doc = row.get("datemissao", "")
            
            if data_doc and "T" in data_doc:
                data_doc = data_doc.split("T")[0]
            elif data_doc and " " in data_doc:
                data_doc = data_doc.split(" ")[0]
                
            if data_doc:
                num_doc = row.get("numdocumento", "unknown")
                fornecedor = row.get("txtfornecedor", "Unknown")
                
                despesa_node = {
                    "id": f"despesa_{num_doc}_{abs(hash(fornecedor))}",
                    "dataEmissao": data_doc[:10],
                    "ufFornecedor": row.get("sguf", "NA"), 
                    "categoria": categoria,
                    "valorDocumento": valor,
                    "nomeFornecedor": fornecedor
                }
                receipts[dep_id].append(despesa_node)
        
        # Save raw data to Parquet for future runs and for RosieWorker
        if raw_rows:
            try:
                df = pd.DataFrame(raw_rows)
                
                numeric_cols = ["vlrliquido", "vlrglosa"]
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.replace(",", ".").replace("", "0")
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
                for col in df.columns:
                    if col not in numeric_cols:
                        df[col] = df[col].astype(str)
                
                self.output_dir.mkdir(parents=True, exist_ok=True)
                df.to_parquet(self.parquet_path, index=False)
                logger.info(f"💾 Raw data saved to Parquet: {self.parquet_path}")
            except Exception as e:
                logger.error(f"❌ Failed to save raw Parquet data: {e}")
                
        return totals, receipts

    def run(self, limit: int = 50):
        """Main execution: fetch deputies, mass process CSV, push to backend."""
        logger.info(f"=== Expenses Worker - Extracting 100% of {self.year} expenses ===")
        
        deputies = self._fetch_all_deputies()
        target_deputies = deputies[:limit]
        target_ids = {d["id"] for d in target_deputies}
        
        logger.info(f"Found {len(deputies)} deputies. Processing first {limit} via Bulk Data...")

        totals_dict, receipts_dict = self._mass_download_and_parse(target_ids)

        for i, dep in enumerate(target_deputies):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"

            total_expenses = round(totals_dict.get(dep_id, 0.0), 2)
            notas_count = len(receipts_dict.get(dep_id, []))
            
            logger.info(f"[{i+1}/{limit}] {name} -> Total: R$ {total_expenses:,.2f} ({notas_count} notas registradas)")
            
            # Injeta 100% das notas no Backend
            for receipt in receipts_dict.get(dep_id, []):
                self.backend.ingest_despesa(external_id, receipt)

            # Injeta o Político com o total atualizado
            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "expenses": total_expenses
            })

        logger.info("=== Expenses Worker Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker de Gastos com Lógica Turicas (100% Dados)")
    parser.add_argument("--limit", type=int, default=15, help="Number of parliamentarians to process")
    args = parser.parse_args()
    
    worker = ExpensesWorker(year=2025)
    worker.run(limit=args.limit)