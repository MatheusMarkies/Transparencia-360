"""
Expenses Worker - Extracts real expense data from the Câmara dos Deputados.

Strategy: Uses the "Turicas Logic" to mass-download the yearly ZIP file,
fixes broken string patterns in memory, saves a CLEAN LOCAL CSV CACHE, 
and pushes EVERY receipt to the backend to maintain a 360 view of the expenses.
"""

import sys
import io
import csv
import zipfile
import requests
import argparse
from pathlib import Path
from collections import defaultdict

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
        # Define o caminho do Cache em CSV
        self.output_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ceap"
        self.csv_path = self.output_dir / f"ceap_{self.year}.csv"

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

    def _mass_download_and_parse(self, target_ids: set):
        """Baixa o ZIP, repara, guarda o CSV local e processa as notas."""
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # === OTIMIZAÇÃO: LER DO CSV CACHE SE EXISTIR ===
        if self.csv_path.exists():
            logger.info(f"📂 Encontrado CSV local {self.csv_path}. Pulando download do Governo...")
        else:
            url = f"https://www.camara.leg.br/cotas/Ano-{self.year}.csv.zip"
            logger.info(f"📥 Baixando pacote massivo do CEAP {self.year} (Logica Turicas)...")
            
            response = requests.get(url, stream=True, timeout=60)
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
                
            logger.info(f"🧹 Sanitizando e salvando base de dados localmente em {self.csv_path}...")
            
            # Lê o stream corrompido, corrige-o e escreve o ficheiro limpo
            with zip_file.open(filename) as zf:
                fobj = FixCSVWrapper(zf, encoding="utf-8-sig", replace=replace_rules)
                with open(self.csv_path, "w", encoding="utf-8") as out_csv:
                    for line in fobj:
                        out_csv.write(line)
        
        logger.info("📊 Extraindo notas fiscais do CSV...")
        totals = defaultdict(float)
        receipts = defaultdict(list)
        
        # Aumentar o limite para não quebrar em descrições enormes
        csv.field_size_limit(1024 ** 2)
        
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            
            for row in reader:
                # Normaliza as chaves
                row_lower = {k.lower(): v for k, v in row.items() if k}
                
                # Pegar o ID com segurança
                dep_id_raw = row_lower.get("idecadastro", "") or row_lower.get("idcadastro", "")
                dep_id_raw = str(dep_id_raw).strip().split('.')[0] # Tira decimais
                
                if not dep_id_raw.isdigit():
                    continue
                    
                dep_id = int(dep_id_raw)
                
                # SE O ID NÃO FOR O DO NOSSO DEPUTADO, DESCARTA IMEDIATAMENTE A NOTA FISCAL
                if dep_id not in target_ids:
                    continue
                    
                try:
                    valor = float(row_lower.get("vlrliquido", "0").replace(",", "."))
                except ValueError:
                    valor = 0.0
                    
                totals[dep_id] += valor
                
                categoria = row_lower.get("txtdescricao", "").strip().upper()
                data_doc = row_lower.get("datemissao", "")
                
                if data_doc and "T" in data_doc:
                    data_doc = data_doc.split("T")[0]
                elif data_doc and " " in data_doc:
                    data_doc = data_doc.split(" ")[0]
                    
                if data_doc:
                    num_doc = row_lower.get("numdocumento", "unknown")
                    fornecedor = row_lower.get("txtfornecedor", "Unknown")
                    
                    # Define ID determinístico para não duplicar nós no Neo4j entre execuções
                    import hashlib
                    hash_fornecedor = hashlib.md5(fornecedor.encode("utf-8")).hexdigest()[:15]
                    
                    despesa_node = {
                        "id": f"despesa_{num_doc}_{hash_fornecedor}",
                        "dataEmissao": data_doc[:10],
                        "ufFornecedor": row_lower.get("sguf", "NA"), 
                        "categoria": categoria,
                        "valorDocumento": valor,
                        "nomeFornecedor": fornecedor
                    }
                    receipts[dep_id].append(despesa_node)
                    
        return totals, receipts

    def run(self, limit: int = 50):
        """Main execution: fetch deputies, mass process CSV, push to backend."""
        logger.info(f"=== Expenses Worker - Extracting 100% of {self.year} expenses ===")
        
        deputies = self._fetch_all_deputies()
        target_deputies = deputies[:limit]
        target_ids = {d["id"] for d in target_deputies}
        
        logger.info(f"Found {len(deputies)} deputies. Processing first {limit} via Bulk CSV...")

        totals_dict, receipts_dict = self._mass_download_and_parse(target_ids)

        for i, dep in enumerate(target_deputies):
            dep_id = dep["id"]
            name = dep["nome"]
            external_id = f"camara_{dep_id}"

            total_expenses = round(totals_dict.get(dep_id, 0.0), 2)
            notas_count = len(receipts_dict.get(dep_id, []))
            
            logger.info(f"[{i+1}/{limit}] {name} -> Total: R$ {total_expenses:,.2f} ({notas_count} notas registradas)")
            
            # Injeta as notas no Backend
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
    parser = argparse.ArgumentParser(description="Worker de Gastos (CSV Cache Direto)")
    parser.add_argument("--limit", type=int, default=15, help="Number of parliamentarians to process")
    args = parser.parse_args()
    
    worker = ExpensesWorker(year=2025)
    worker.run(limit=args.limit)