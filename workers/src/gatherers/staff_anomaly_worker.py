"""
Staff Anomaly Worker - Detects ghost employees, nepotism, and suspicious payments.

Uses a combination of heuristic rules and Isolation Forest (unsupervised ML)
to detect anomalies in deputy expense data (fornecedores/suppliers).

== Detection Pipeline ==
1. Data Collection: Fetch all expense records for each deputy from the Câmara API
2. Supplier Aggregation: Group by supplier name, compute total value and frequency
3. Heuristic Rules:
   a) Nepotism: Surname match between deputy and frequent suppliers
   b) Super-Payment: Suppliers receiving >3x standard deviation above mean
   c) Concentration: Suppliers getting paid by only ONE deputy (100% concentration)
4. Isolation Forest: Train on (total_value, frequency, concentration) features
   to detect multi-dimensional outliers

Results are stored as staffAnomalyCount + staffAnomalyDetails (JSON) per politician.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import requests
import json
import unicodedata
import numpy as np
from collections import defaultdict
from src.core.api_client import BackendClient, GovAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"


def normalize_name(name: str) -> str:
    """Remove accents, uppercase."""
    name = unicodedata.normalize('NFKD', name.upper()).encode('ASCII', 'ignore').decode('ASCII')
    return name.strip()


def extract_surnames(name: str) -> set:
    """Extract possible surnames from a full name (words with >=3 chars, ignoring common prefixes)."""
    ignore = {'DA', 'DE', 'DO', 'DAS', 'DOS', 'DR', 'DRA', 'JR', 'JUNIOR', 'NETO', 'FILHO', 'SOBRINHO'}
    parts = normalize_name(name).split()
    return {p for p in parts if len(p) >= 3 and p not in ignore}


class StaffAnomalyWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.camara = GovAPIClient(CAMARA_API, request_delay=0.15)

    def _fetch_deputy_expenses(self, dep_id: int, year: int = 2025) -> list:
        """Fetch all expense records for a deputy in a given year."""
        all_expenses = []
        page = 1
        while True:
            resp = self.camara.get(f"deputados/{dep_id}/despesas", params={
                "ano": year,
                "pagina": page,
                "itens": 100,
                "ordem": "DESC",
                "ordenarPor": "valorLiquido"
            })
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            all_expenses.extend(resp["dados"])
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
        return all_expenses

    def _aggregate_suppliers(self, expenses: list) -> dict:
        """Group expenses by supplier name, computing total value and frequency."""
        suppliers: dict[str, dict] = {}
        for exp in expenses:
            nome = exp.get("nomeFornecedor", "").strip()
            if not nome or len(nome) < 3:
                continue
            if nome not in suppliers:
                suppliers[nome] = {"total": 0.0, "count": 0, "types": set()}
            valor = float(exp.get("valorLiquido", 0.0))
            tipo = str(exp.get("tipoDespesa", ""))
            suppliers[nome]["total"] += valor
            suppliers[nome]["count"] += 1
            suppliers[nome]["types"].add(tipo)
        # Convert sets to lists for serialization
        for s in suppliers.values():
            s["types"] = list(s["types"])
        return suppliers

    def run(self, limit: int = 50):
        logger.info("=== Staff Anomaly Worker - Ghost Employee & Nepotism Detection ===")

        # Step 1: Fetch all deputies
        logger.info("Step 1: Fetching deputies...")
        camara_deps = []
        page = 1
        while True:
            resp = self.camara.get("deputados", params={
                "pagina": page, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"
            })
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            camara_deps.extend(resp["dados"])
            links = resp.get("links", [])
            if not any(l.get("rel") == "next" for l in links):
                break
            page += 1
        logger.info(f"  Found {len(camara_deps)} deputies")

        # Step 2: Collect expense data for all deputies to build global supplier profile
        logger.info("Step 2: Collecting expense data...")
        deputy_suppliers: dict[int, dict] = {}  # dep_id -> {supplier_name -> {total, count, types}}
        global_suppliers: dict[str, dict] = {}

        for dep in camara_deps[:limit]:
            dep_id = int(dep["id"])
            dep_name = str(dep["nome"])
            expenses = self._fetch_deputy_expenses(dep_id)
            suppliers = self._aggregate_suppliers(expenses)
            deputy_suppliers[dep_id] = {"name": dep_name, "suppliers": suppliers}

            # Build global supplier profile
            for supplier_name, data in suppliers.items():
                if supplier_name not in global_suppliers:
                    global_suppliers[supplier_name] = {"total": 0.0, "count": 0, "deputies": set()}
                global_suppliers[supplier_name]["total"] += float(data["total"])
                global_suppliers[supplier_name]["count"] += int(data["count"])
                global_suppliers[supplier_name]["deputies"].add(dep_id)

            logger.info(f"  {dep_name}: {len(expenses)} expenses, {len(suppliers)} unique suppliers")

        # Step 3: Apply heuristic rules + Isolation Forest
        logger.info("Step 3: Running anomaly detection...")

        # Compute global statistics for thresholds
        all_totals = [s["total"] for s in global_suppliers.values() if s["total"] > 0]
        if not all_totals:
            logger.warning("No expense data found. Aborting.")
            return

        mean_total = np.mean(all_totals)
        std_total = np.std(all_totals)
        threshold_super_payment = mean_total + 3 * std_total

        logger.info(f"  Global stats: mean=R${mean_total:,.0f}, std=R${std_total:,.0f}, threshold=R${threshold_super_payment:,.0f}")

        # Prepare Isolation Forest features
        feature_matrix = []
        supplier_keys = []
        for name, data in global_suppliers.items():
            dep_count = len(data["deputies"])
            concentration = 1.0 / dep_count  # 1.0 = only one deputy uses this supplier
            feature_matrix.append([
                data["total"],
                data["count"],
                concentration,
            ])
            supplier_keys.append(name)

        # Train Isolation Forest
        from sklearn.ensemble import IsolationForest
        iso_forest = None
        iso_predictions = {}
        if len(feature_matrix) >= 10:
            X = np.array(feature_matrix)
            iso_forest = IsolationForest(
                contamination=0.1,  # Expect ~10% anomalies
                random_state=42,
                n_estimators=100
            )
            predictions = iso_forest.fit_predict(X)
            scores = iso_forest.decision_function(X)
            for i, key in enumerate(supplier_keys):
                iso_predictions[key] = {
                    "is_anomaly": predictions[i] == -1,
                    "score": round(float(scores[i]), 4)
                }
            anomaly_count = sum(1 for p in predictions if p == -1)
            logger.info(f"  Isolation Forest: {anomaly_count}/{len(predictions)} suppliers flagged as anomalous")

        # Step 4: Generate per-deputy anomaly reports
        logger.info("Step 4: Generating anomaly reports per deputy...")

        for dep in camara_deps[:limit]:
            dep_id = dep["id"]
            dep_name = dep["nome"]
            external_id = f"camara_{dep_id}"
            dep_surnames = extract_surnames(dep_name)

            dep_data = deputy_suppliers.get(dep_id, {"suppliers": {}})
            suppliers = dep_data.get("suppliers", {})

            anomalies = []

            for supplier_name, data in suppliers.items():
                supplier_norm = normalize_name(supplier_name)
                supplier_surnames = extract_surnames(supplier_name)
                flags = []

                # Heuristic 1: Nepotism (surname match)
                common_surnames = dep_surnames & supplier_surnames
                if common_surnames and data["total"] > 5000:
                    flags.append({
                        "type": "NEPOTISMO",
                        "severity": "HIGH",
                        "detail": f"Sobrenome em comum: {', '.join(common_surnames)}. Total recebido: R${data['total']:,.2f}"
                    })

                # Heuristic 2: Super-Payment (>3x std dev)
                if data["total"] > threshold_super_payment:
                    flags.append({
                        "type": "SUPER_PAGAMENTO",
                        "severity": "MEDIUM",
                        "detail": f"Recebeu R${data['total']:,.2f} (limiar: R${threshold_super_payment:,.2f})"
                    })

                # Heuristic 3: Concentration (only works with this ONE deputy)
                global_data = global_suppliers.get(supplier_name, {"deputies": set()})
                if len(global_data["deputies"]) == 1 and data["total"] > 50000 and data["count"] >= 5:
                    flags.append({
                        "type": "CONCENTRACAO",
                        "severity": "MEDIUM",
                        "detail": f"Recebe apenas deste deputado. {data['count']} pagamentos totalizando R${data['total']:,.2f}"
                    })

                # Isolation Forest anomaly
                iso_data = iso_predictions.get(supplier_name, {"is_anomaly": False})
                if iso_data["is_anomaly"] and not flags:
                    flags.append({
                        "type": "ML_ANOMALIA",
                        "severity": "LOW",
                        "detail": f"Detectado por Isolation Forest (score: {iso_data.get('score', 0):.4f})"
                    })

                if flags:
                    anomalies.append({
                        "supplier": supplier_name,
                        "totalValue": round(data["total"], 2),
                        "paymentCount": data["count"],
                        "flags": flags
                    })

            # Persist results
            anomaly_count = len(anomalies)
            if anomaly_count > 0:
                # Sort by severity
                severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
                anomalies.sort(key=lambda a: min(severity_order.get(f["severity"], 3) for f in a["flags"]))

                logger.info(f"  🚩 {dep_name}: {anomaly_count} suspicious suppliers found")
                for a in anomalies[:3]:
                    for f in a["flags"]:
                        logger.info(f"    [{f['type']}] {a['supplier']}: {f['detail']}")

            # Only store top 10 anomalies to keep JSON manageable
            details_json = json.dumps(anomalies[:10], ensure_ascii=False) if anomalies else "[]"

            self.backend.ingest_politician({
                "externalId": external_id,
                "name": dep_name,
                "party": dep.get("siglaPartido"),
                "state": dep.get("siglaUf"),
                "position": "Deputado Federal",
                "staffAnomalyCount": anomaly_count,
                "staffAnomalyDetails": details_json
            })

        logger.info("=== Staff Anomaly Worker Complete ===")


if __name__ == "__main__":
    worker = StaffAnomalyWorker()
    worker.run(limit=50)
