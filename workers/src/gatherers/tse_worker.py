"""
TSE Worker - Extracts electoral data from the Tribunal Superior Eleitoral.

Downloads and processes candidate data from 3 election years (2014, 2018, 2022)
to track patrimonial evolution. Matches TSE candidates to Câmara deputies
by normalized name and persists aggregated declared assets per year.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import requests
import zipfile
import csv
import os
import tempfile
import unicodedata
import shutil
from src.core.api_client import BackendClient, GovAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TSE_URLS = {
    2014: {
        "cand": "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2014.zip",
        "bens": "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2014.zip",
    },
    2018: {
        "cand": "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2018.zip",
        "bens": "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2018.zip",
    },
    2022: {
        "cand": "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2022.zip",
        "bens": "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2022.zip",
    },
}


import polars as pl

def normalize_name(name: str) -> str:
    """Normalize name for matching: uppercase, remove accents."""
    if not name: return ""
    name = unicodedata.normalize('NFKD', name.upper()).encode('ASCII', 'ignore').decode('ASCII')
    return name.strip()

class TSEWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.temp_dir = tempfile.mkdtemp(prefix="tp360_tse_")

    def _download_and_extract(self, url: str, prefix: str) -> str:
        logger.info(f"  Downloading {url}...")
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        zip_path = os.path.join(self.temp_dir, f"{prefix}.zip")
        with open(zip_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"    -> {len(resp.content) / 1024 / 1024:.1f} MB")
        extract_dir = os.path.join(self.temp_dir, prefix)
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_dir)
        return extract_dir

    def _process_year(self, year: int) -> dict:
        """Download and process data for a single election year using Polars.
        Returns dict mapping normalized ballot name -> total assets."""
        urls = TSE_URLS[year]
        logger.info(f"--- Processing {year} (Polars Engine) ---")

        # 1. Process Candidates
        cand_dir = Path(self._download_and_extract(urls["cand"], f"cand_{year}"))
        cand_files = list(cand_dir.glob("**/*.csv"))
        
        cand_dfs = []
        for f in cand_files:
            try:
                # TSE files usually use latin-1 and semicolon
                df = pl.read_csv(f, separator=";", encoding="latin-1", infer_schema_length=0)
                # DS_CARGO is the column name in recent files, DESCRICAO_CARGO in older ones
                cargo_col = "DS_CARGO" if "DS_CARGO" in df.columns else "DESCRICAO_CARGO"
                sit_col = "DS_SIT_TOT_TURNO" if "DS_SIT_TOT_TURNO" in df.columns else "DESC_SIT_TOT_TURNO"
                nome_col = "NM_URNA_CANDIDATO" if "NM_URNA_CANDIDATO" in df.columns else "NOME_URNA_CANDIDATO"
                sq_col = "SQ_CANDIDATO" if "SQ_CANDIDATO" in df.columns else "SEQUENCIAL_CANDIDATO"
                
                df_fil = df.filter(
                    pl.col(cargo_col).str.to_uppercase().str.contains("DEPUTADO FEDERAL") &
                    (pl.col(sit_col).str.to_uppercase().str.contains("ELEITO") | 
                     pl.col(sit_col).str.to_uppercase().str.contains("MEDIA") |
                     pl.col(sit_col).str.to_uppercase().str.contains("SUPLENTE"))
                ).select([
                    pl.col(nome_col).alias("nome_urna"),
                    pl.col(sq_col).alias("sq")
                ])
                cand_dfs.append(df_fil)
            except Exception as e:
                logger.warning(f"Error parsing {f.name}: {e}")

        if not cand_dfs: return {}
        candidates_df = pl.concat(cand_dfs).unique(subset=["sq"])
        
        # 2. Process Assets
        bens_dir = Path(self._download_and_extract(urls["bens"], f"bens_{year}"))
        bens_files = list(bens_dir.glob("**/*.csv"))
        
        bens_dfs = []
        for f in bens_files:
            try:
                df_bens = pl.read_csv(f, separator=";", encoding="latin-1", infer_schema_length=0)
                sq_col_bens = "SQ_CANDIDATO" if "SQ_CANDIDATO" in df_bens.columns else "SEQUENCIAL_CANDIDATO"
                val_col = "VR_BEM_CANDIDATO" if "VR_BEM_CANDIDATO" in df_bens.columns else "VALOR_BEM"
                
                df_bens = df_bens.select([
                    pl.col(sq_col_bens).alias("sq"),
                    pl.col(val_col).str.replace(",", ".").cast(pl.Float64, strict=False).fill_null(0.0).alias("valor")
                ])
                bens_dfs.append(df_bens)
            except Exception as e:
                logger.warning(f"Error parsing assets {f.name}: {e}")

        if not bens_dfs: return {}
        assets_df = pl.concat(bens_dfs)
        
        # 3. Join and Aggregate
        final_df = candidates_df.join(assets_df, on="sq")
        agg_df = final_df.group_by("nome_urna").agg(pl.col("valor").sum().alias("total_bens"))
        
        # Convert to dict with normalized names
        result = {}
        for row in agg_df.to_dicts():
            norm = normalize_name(row["nome_urna"])
            result[norm] = row["total_bens"]
            
        logger.info(f"  {year}: {len(result)} candidates with Polars-aggregated assets")
        return result

    def run(self, limit: int = 50):
        logger.info("=== TSE Worker - Multi-Year Patrimonial Evolution ===")

        # Process all 3 election years
        assets_2014 = self._process_year(2014)
        assets_2018 = self._process_year(2018)
        assets_2022 = self._process_year(2022)

        # Fetch Câmara deputies to match
        logger.info("Matching with Câmara deputies...")
        camara = GovAPIClient("https://dadosabertos.camara.leg.br/api/v2", request_delay=0.2)
        camara_deps = []
        page = 1
        while True:
            resp = camara.get("deputados", params={"pagina": page, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"})
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            camara_deps.extend(resp["dados"])
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1

        matched = 0
        for dep in camara_deps[:limit]:
            dep_name = dep["nome"]
            dep_norm = normalize_name(dep_name)
            external_id = f"camara_{dep['id']}"

            a22 = assets_2022.get(dep_norm)
            a18 = assets_2018.get(dep_norm)
            a14 = assets_2014.get(dep_norm)

            # Try partial match if exact match fails
            if a22 is None and a18 is None and a14 is None:
                for norm_key in assets_2022:
                    if dep_norm in norm_key or norm_key in dep_norm:
                        a22 = assets_2022[norm_key]
                        a18 = assets_2018.get(norm_key)
                        a14 = assets_2014.get(norm_key)
                        break

            if a22 is not None or a18 is not None or a14 is not None:
                payload = {
                    "externalId": external_id,
                    "name": dep_name,
                    "party": dep.get("siglaPartido"),
                    "state": dep.get("siglaUf"),
                    "position": "Deputado Federal",
                }
                if a22 is not None:
                    payload["declaredAssets"] = round(a22, 2)
                if a18 is not None:
                    payload["declaredAssets2018"] = round(a18, 2)
                if a14 is not None:
                    payload["declaredAssets2014"] = round(a14, 2)

                growth = ""
                if a14 and a22 and a14 > 0:
                    pct = ((a22 - a14) / a14) * 100
                    growth = f" | Crescimento: {pct:+.0f}%"

                logger.info(f"  {dep_name}: 2014=R${a14 or 0:,.0f} -> 2018=R${a18 or 0:,.0f} -> 2022=R${a22 or 0:,.0f}{growth}")
                self.backend.ingest_politician(payload)
                matched += 1

        logger.info(f"=== TSE Worker Complete - {matched}/{limit} deputies with asset history ===")

        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    worker = TSEWorker()
    parser.add_argument("--limit", type=int, default=15, help="Number of parliamentarians to process")
    args = parser.parse_args()
    worker.run(limit=args.limit)
