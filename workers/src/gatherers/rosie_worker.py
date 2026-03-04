"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ROSIE WORKER v2.0 — Integration Layer                                     ║
║                                                                            ║
║  Plugs into run_all_extractions.py as a new Step.                          ║
║  Reads CEAP bulk CSV (same as expenses_worker.py), runs all 12 Rosie       ║
║  classifiers, and pushes anomaly findings to the Backend API + Neo4j.      ║
║                                                                            ║
║  This worker is designed to run AFTER expenses_worker.py (Step 4) so       ║
║  that both the raw data AND the anomaly layer coexist.                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import io
import csv
import json
import zipfile
import logging
import argparse
import requests
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Optional
from src.gatherers.rosie_engine import RosieEngine

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("rosie_worker")


# =============================================================================
# CSV FIX (same Turicas logic from expenses_worker.py)
# =============================================================================

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


# =============================================================================
# BLACKLIST LOADER (Portal da Transparência CEIS/CNEP)
# =============================================================================

class BlacklistLoader:
    """
    Downloads CEIS (Cadastro de Empresas Inidôneas e Suspensas) and
    CNEP (Cadastro Nacional de Empresas Punidas) from Portal da Transparência.
    """

    PORTAL_API = "https://api.portaldatransparencia.gov.br/api-de-dados"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PORTAL_API_KEY", "")
        self.blacklisted_cnpjs: set = set()

    def load(self) -> set:
        """Attempt to load CEIS + CNEP. Returns set of CNPJ strings."""
        if not self.api_key:
            logger.warning("[BlacklistLoader] No PORTAL_API_KEY. Skipping CEIS/CNEP download.")
            return self._load_from_cache()

        headers = {"chave-api-dados": self.api_key, "Accept": "application/json"}

        for endpoint, name in [("ceis", "CEIS"), ("cnep", "CNEP")]:
            try:
                logger.info(f"[BlacklistLoader] Downloading {name}...")
                page = 1
                while page <= 20:  # Safety limit
                    resp = requests.get(
                        f"{self.PORTAL_API}/{endpoint}",
                        headers=headers,
                        params={"pagina": page},
                        timeout=30,
                    )
                    if resp.status_code != 200:
                        logger.warning(f"  {name} page {page}: HTTP {resp.status_code}")
                        break

                    data = resp.json()
                    if not data:
                        break

                    for entry in data:
                        cnpj = (
                            entry.get("cnpjSancionado", "") or
                            entry.get("pessoaJuridica", {}).get("cnpjFormatado", "") or
                            ""
                        )
                        cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "").strip()
                        if cnpj_clean and len(cnpj_clean) >= 11:
                            self.blacklisted_cnpjs.add(cnpj_clean)

                    page += 1

                logger.info(f"  {name}: loaded (total blacklist: {len(self.blacklisted_cnpjs)})")
            except Exception as e:
                logger.error(f"  Error loading {name}: {e}")

        # Save cache
        self._save_cache()
        return self.blacklisted_cnpjs

    def _cache_path(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed" / "blacklist_cache.json"

    def _save_cache(self):
        try:
            path = self._cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(list(self.blacklisted_cnpjs), f)
        except Exception as e:
            logger.warning(f"  Cache save failed: {e}")

    def _load_from_cache(self) -> set:
        try:
            path = self._cache_path()
            if path.exists():
                with open(path, "r") as f:
                    data = json.load(f)
                self.blacklisted_cnpjs = set(data)
                logger.info(f"[BlacklistLoader] Loaded {len(self.blacklisted_cnpjs)} CNPJs from cache")
        except Exception as e:
            logger.warning(f"  Cache load failed: {e}")
        return self.blacklisted_cnpjs


# =============================================================================
# MAIN ROSIE WORKER
# =============================================================================

class RosieWorker:
    """
    Production worker that:
    1. Downloads CEAP bulk CSV (same source as expenses_worker)
    2. Parses ALL receipts (not just filtered categories)
    3. Runs the full Rosie engine (12 classifiers)
    4. Pushes anomaly findings to the backend API
    5. Saves detailed JSON report to data/processed/
    """

    # ALL categories (not filtered like expenses_worker)
    ALL_CATEGORIES = True

    def __init__(self, years: List[int] = None, backend_url: str = "http://localhost:8080"):
        self.years = years or [2024, 2025]
        self.backend_url = backend_url

    def _download_and_parse_full(self, year: int, target_ids: Optional[set] = None) -> List[Dict]:
        """
        Lê o CEAP do disco local (Parquet) gerado pelo ExpensesWorker,
        e converte para a lista exata de dicionários que o RosieEngine precisa.
        """
        import pandas as pd
        
        parquet_path = Path(f"data/raw/camara/ceap_{year}_raw.parquet")
        
        logger.info(f"📥 Loading CEAP {year} from Parquet file (skipping download)..")
        
        if not parquet_path.exists():
            logger.error(f"  ❌ File not found: {parquet_path}")
            return []

        # Lê o ficheiro local ultrarrápido
        df = pd.read_parquet(parquet_path)
        logger.info(f"  🧹 Parsing {len(df)} rows from Parquet for year {year}...")

        # Se houver target_ids (ex: limit 2), filtra os dados logo no pandas para ser mais rápido
        if target_ids:
            # O parquet pode ter os IDs como float/int/string. Forçamos para inteiro para garantir.
            df = df[df['deputado_id'].astype(str).str.replace(r'\.0$', '', regex=True).isin([str(tid) for tid in target_ids])]

        receipts = []
        skipped = 0

        # Iterar sobre o dataframe para gerar o formato que a Rosie conhece perfeitamente
        for _, row in df.iterrows():
            dep_id_str = str(row.get('deputado_id', '')).replace('.0', '')
            if not dep_id_str or dep_id_str.lower() in ('nan', 'none'):
                skipped += 1
                continue
                
            dep_id = int(dep_id_str)
            
            valor = row.get('valorLiquido', 0.0)
            if pd.isna(valor) or valor <= 0:
                skipped += 1
                continue

            data_doc = str(row.get('dataDocumento', ''))
            if data_doc and 'T' in data_doc:
                data_doc = data_doc.split('T')[0]
            elif data_doc and ' ' in data_doc:
                data_doc = data_doc.split(' ')[0]

            # Construir o recibo exatamente como a Rosie Engine quer ler
            receipt = {
                "id": f"ceap_{year}_{row.get('numdocumento', '')}_{dep_id}_{abs(hash(str(row.get('nomeFornecedor', ''))))}",
                "deputy_id": str(dep_id),
                "deputy_name": str(row.get("deputado_nome", "")).strip(),
                "party": str(row.get("deputado_siglaPartido", "")).strip(),
                "ufDeputado": str(row.get("siglaUF", "")).strip(),
                "dataEmissao": data_doc[:10] if data_doc and data_doc.lower() != 'nan' else "",
                "categoria": str(row.get("tipoDespesa", "")).strip(),
                "subcategoria": str(row.get("txtdescricaoespecificacao", "")).strip(),
                "valorDocumento": float(row.get('valorDocumento', 0.0) if not pd.isna(row.get('valorDocumento')) else 0.0),
                "valorGlosa": 0.0, # Nós usamos valorLiquido no Parquet diretamente
                "nomeFornecedor": str(row.get("nomeFornecedor", "")).strip(),
                "cnpjFornecedor": str(row.get("cnpjCpfFornecedor", "")).strip(),
                "ufFornecedor": str(row.get("siglaUF", "NA")), # UF do Deputado no CEAP original
                "numDocumento": str(row.get("numdocumento", "")).strip(),
                "numLote": str(row.get("numlote", "")).strip(),
                "numParcela": str(row.get("numparcela", "")).strip(),
                "year": year,
            }
            receipts.append(receipt)

        logger.info(f"  ✅ Parsed {len(receipts)} valid receipts (skipped {skipped} invalid/zero-value rows)")
        return receipts

    def _fetch_deputy_ids(self, limit: int) -> set:
        """Fetch active deputy IDs from the Câmara API."""
        try:
            all_ids = set()
            page = 1
            while True:
                resp = requests.get(
                    "https://dadosabertos.camara.leg.br/api/v2/deputados",
                    params={"pagina": page, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"},
                    timeout=30,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data.get("dados"):
                    break
                for d in data["dados"]:
                    all_ids.add(d["id"])
                if not any(l.get("rel") == "next" for l in data.get("links", [])):
                    break
                page += 1

            # Apply limit
            return set(sorted(all_ids)[:limit]) if limit else all_ids

        except Exception as e:
            logger.error(f"  Failed to fetch deputy IDs: {e}")
            return set()

    def _push_anomalies_to_backend(self, report: Dict):
        """Push Rosie findings to the backend API."""
        try:
            # Push per-deputy risk scores
            for dep_id, scores in report.get("deputy_risk_scores", {}).items():
                external_id = f"camara_{dep_id}"
                payload = {
                    "externalId": external_id,
                    "rosieRiskScore": scores["risk_score"],
                    "rosieAnomalies": scores["n_anomalies"],
                    "rosieClassifiersTriggered": scores["n_classifiers_triggered"],
                    "rosieTopFindings": [
                        {
                            "classifier": a["classifier"],
                            "confidence": a["confidence"],
                            "reason": a["reason"],
                        }
                        for a in scores.get("top_anomalies", [])[:5]
                    ],
                }

                resp = requests.post(
                    f"{self.backend_url}/api/internal/workers/ingest/rosie-score",
                    json=payload,
                    timeout=10,
                )
                if resp.status_code not in (200, 201, 204):
                    # Fallback: try alternative endpoint
                    resp2 = requests.put(
                        f"{self.backend_url}/api/internal/workers/ingest/politician/{external_id}/rosie",
                        json=payload,
                        timeout=10,
                    )
                    if resp2.status_code not in (200, 201, 204):
                        logger.debug(f"  Backend push for {external_id}: HTTP {resp2.status_code}")

        except requests.RequestException as e:
            logger.warning(f"  Backend push failed (non-critical): {e}")

    def _save_report(self, report: Dict, filename: str = "rosie_report.json"):
        """Save the full Rosie report to data/processed/."""
        try:
            base_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"
            base_path.mkdir(parents=True, exist_ok=True)

            filepath = base_path / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"  💾 Full report saved to: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"  Failed to save report: {e}")
            return None

    def _save_anomalies_csv(self, report: Dict, filename: str = "rosie_anomalies.csv"):
        """Save anomalies as CSV for easy consumption."""
        try:
            base_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"
            base_path.mkdir(parents=True, exist_ok=True)

            filepath = base_path / filename

            anomalies = report.get("all_anomalies", [])
            if not anomalies:
                return None

            fieldnames = [
                "deputy_id", "receipt_id", "classifier",
                "confidence", "reason",
            ]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for a in anomalies:
                    writer.writerow({
                        "deputy_id": a.get("deputy_id", ""),
                        "receipt_id": a.get("receipt_id", ""),
                        "classifier": a.get("classifier", ""),
                        "confidence": a.get("confidence", 0),
                        "reason": a.get("reason", ""),
                    })

            logger.info(f"  📊 Anomalies CSV saved to: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"  Failed to save CSV: {e}")
            return None

    def run(self, limit: int = 100):
        """
        Main execution flow:
        1. Load blacklists (CEIS/CNEP)
        2. Fetch deputy IDs
        3. Download + parse CEAP CSVs
        4. Run Rosie engine
        5. Push results + save reports
        """
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║  🤖 ROSIE WORKER v2.0 — Full Anomaly Detection         ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")
        start_time = datetime.now()

        # Step 1: Load blacklists
        logger.info("\n📋 Step 1: Loading CEIS/CNEP blacklists...")
        bl = BlacklistLoader()
        blacklist = bl.load()

        # Step 2: Get deputy IDs
        logger.info(f"\n👥 Step 2: Fetching deputy IDs (limit={limit})...")
        target_ids = self._fetch_deputy_ids(limit)
        logger.info(f"  Found {len(target_ids)} deputies")

        # Step 3: Download and parse CEAP data
        logger.info("\n📥 Step 3: Downloading CEAP data...")
        all_receipts = []
        for year in self.years:
            receipts = self._download_and_parse_full(year, target_ids)
            all_receipts.extend(receipts)

        if not all_receipts:
            logger.error("  ❌ No receipts found. Aborting.")
            return

        logger.info(f"  📊 Total receipts across all years: {len(all_receipts)}")

        # Step 4: Initialize and run Rosie
        logger.info("\n🤖 Step 4: Running Rosie Engine...")
        rosie = RosieEngine(
            blacklist_cnpjs=blacklist,
            company_dates=None,  # Will be enriched when Receita Federal data is available
            enable_all=True,
        )

        report = rosie.analyze(all_receipts)

        # Step 5: Push to backend
        logger.info("\n📤 Step 5: Pushing results to backend...")
        self._push_anomalies_to_backend(report)

        # Step 6: Save reports
        logger.info("\n💾 Step 6: Saving reports...")
        self._save_report(report, "rosie_report.json")
        self._save_anomalies_csv(report, "rosie_anomalies.csv")

        # Summary with risk ranking
        self._save_risk_ranking(report)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n{'='*60}")
        logger.info(f"  🤖 ROSIE WORKER COMPLETE — {elapsed:.1f}s")
        logger.info(f"  Receipts analyzed: {len(all_receipts)}")
        logger.info(f"  Anomalies found:   {report['summary']['total_anomalies']}")
        logger.info(f"  Deputies flagged:  {report['summary']['deputies_with_anomalies']}")
        logger.info(f"{'='*60}\n")

        return report

    def _save_risk_ranking(self, report: Dict):
        """Save a human-readable risk ranking."""
        try:
            base_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"
            filepath = base_path / "rosie_risk_ranking.txt"

            lines = [
                "=" * 70,
                "  ROSIE RISK RANKING — Deputies by Anomaly Score",
                f"  Generated: {datetime.now().isoformat()}",
                "=" * 70,
                "",
            ]

            top_deputies = report.get("summary", {}).get("top_risk_deputies", [])
            for rank, (dep_id, scores) in enumerate(top_deputies, 1):
                lines.append(f"  #{rank:02d} | Deputy ID: {dep_id}")
                lines.append(f"       Risk Score: {scores['risk_score']:.1f}/100")
                lines.append(f"       Anomalies: {scores['n_anomalies']}")
                lines.append(f"       Classifiers triggered: {scores['n_classifiers_triggered']}/12")

                for finding in scores.get("top_anomalies", [])[:3]:
                    lines.append(f"       → [{finding['classifier']}] {finding['reason'][:80]}...")

                lines.append("")

            lines.append("=" * 70)
            lines.append(f"  Classifier breakdown:")
            for clf, count in sorted(
                report.get("summary", {}).get("anomalies_by_classifier", {}).items(),
                key=lambda x: -x[1]
            ):
                lines.append(f"    {clf}: {count} anomalies")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            logger.info(f"  📝 Risk ranking saved to: {filepath}")
        except Exception as e:
            logger.error(f"  Failed to save ranking: {e}")


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rosie Worker — Full CEAP Anomaly Detection Engine"
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Number of deputies to analyze"
    )
    parser.add_argument(
        "--years", type=int, nargs="+", default=[2024, 2025],
        help="Years to analyze (e.g., --years 2023 2024 2025)"
    )
    parser.add_argument(
        "--backend", type=str, default="http://localhost:8080",
        help="Backend API URL"
    )
    args = parser.parse_args()

    worker = RosieWorker(years=args.years, backend_url=args.backend)
    worker.run(limit=args.limit)
