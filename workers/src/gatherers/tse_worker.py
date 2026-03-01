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


def normalize_name(name: str) -> str:
    """Normalize name for matching: uppercase, remove accents."""
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

    def _find_csv_files(self, directory: str) -> list:
        csv_files = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.lower().endswith('.csv'):
                    csv_files.append(os.path.join(root, f))
        return csv_files

    def _parse_candidates(self, csv_path: str) -> dict:
        """Returns dict mapping NM_URNA_CANDIDATO -> {sq_candidato, ...}"""
        candidates = {}
        for enc in ['latin-1', 'utf-8', 'cp1252']:
            try:
                with open(csv_path, 'r', encoding=enc) as f:
                    reader = csv.DictReader(f, delimiter=';', quotechar='"')
                    for row in reader:
                        cargo = row.get('DS_CARGO', row.get('DESCRICAO_CARGO', '')).upper()
                        situacao = row.get('DS_SIT_TOT_TURNO', row.get('DESC_SIT_TOT_TURNO', '')).upper()
                        if 'DEPUTADO FEDERAL' in cargo and ('ELEITO' in situacao or 'MÉDIA' in situacao or 'SUPLENTE' in situacao):
                            nome_urna = row.get('NM_URNA_CANDIDATO', row.get('NOME_URNA_CANDIDATO', '')).strip()
                            sq = row.get('SQ_CANDIDATO', row.get('SEQUENCIAL_CANDIDATO', '')).strip()
                            if nome_urna and sq:
                                candidates[nome_urna] = {'sq': sq}
                return candidates
            except (UnicodeDecodeError, KeyError):
                continue
        return candidates

    def _parse_assets(self, csv_path: str, candidates: dict) -> dict:
        """Returns dict mapping NM_URNA -> total assets value."""
        sq_lookup = {info['sq']: name for name, info in candidates.items()}
        assets = {}
        for enc in ['latin-1', 'utf-8', 'cp1252']:
            try:
                with open(csv_path, 'r', encoding=enc) as f:
                    reader = csv.DictReader(f, delimiter=';', quotechar='"')
                    for row in reader:
                        sq = row.get('SQ_CANDIDATO', row.get('SEQUENCIAL_CANDIDATO', '')).strip()
                        if sq not in sq_lookup:
                            continue
                        valor_str = row.get('VR_BEM_CANDIDATO', row.get('VALOR_BEM', '0')).strip().replace(',', '.')
                        try:
                            valor = float(valor_str)
                        except ValueError:
                            valor = 0.0
                        name = sq_lookup[sq]
                        assets[name] = assets.get(name, 0.0) + valor
                return assets
            except (UnicodeDecodeError, KeyError):
                continue
        return assets

    def _process_year(self, year: int) -> dict:
        """Download and process data for a single election year.
        Returns dict mapping normalized ballot name -> total assets."""
        urls = TSE_URLS[year]
        logger.info(f"--- Processing {year} ---")

        # Candidates
        cand_dir = self._download_and_extract(urls["cand"], f"cand_{year}")
        all_candidates = {}
        for csv_path in self._find_csv_files(cand_dir):
            parsed = self._parse_candidates(csv_path)
            all_candidates.update(parsed)
        logger.info(f"  {year}: {len(all_candidates)} federal deputies found")

        # Assets
        bens_dir = self._download_and_extract(urls["bens"], f"bens_{year}")
        all_assets = {}
        for csv_path in self._find_csv_files(bens_dir):
            parsed = self._parse_assets(csv_path, all_candidates)
            for name, total in parsed.items():
                all_assets[name] = max(all_assets.get(name, 0.0), total)
        logger.info(f"  {year}: {len(all_assets)} candidates with asset data")

        # Normalize names for matching
        result = {}
        for nome_urna, total in all_assets.items():
            norm = normalize_name(nome_urna)
            result[norm] = total
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
    worker.run(limit=50)
