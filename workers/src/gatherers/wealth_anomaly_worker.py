"""
Wealth Anomaly Worker - Detects suspicious patrimonial growth.

Compares a politician's declared asset growth (TSE data) against what
would be mathematically possible from their official salary alone.

== Logic ==
A federal deputy earns ~R$44,000/month gross (2024 values).
Over 8 years (2 mandates, 2014-2022) = R$4,224,000 gross.
After income tax (~27.5%) and minimum living costs, realistic
maximum savings ≈ R$2,100,000 over 8 years.

If patrimony grew MORE than this maximum, the excess is flagged.

== Anomaly Score ==
  score = actual_growth / max_possible_savings
  - score < 1.0 → Green: Growth within salary range
  - score 1.0-2.0 → Yellow: Growth slightly above salary
  - score 2.0-5.0 → Orange: Growth significantly above salary
  - score > 5.0 → Red: Growth impossible from salary alone
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import requests
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Official federal deputy salary (monthly, gross)
DEPUTY_MONTHLY_SALARY = 44_000.00
# Tax rate (average effective)
EFFECTIVE_TAX_RATE = 0.275
# Years between elections
YEARS_2014_TO_2022 = 8
# Estimated minimum annual living cost
ANNUAL_LIVING_COST = 120_000.00

# Maximum realistic savings over 8 years from salary alone
ANNUAL_NET = (DEPUTY_MONTHLY_SALARY * 12) * (1 - EFFECTIVE_TAX_RATE) - ANNUAL_LIVING_COST
MAX_SAVINGS_8Y = ANNUAL_NET * YEARS_2014_TO_2022


class WealthAnomalyWorker:
    def __init__(self):
        self.backend = BackendClient()

    def run(self, limit: int = None):
        logger.info("=== Wealth Anomaly Worker ===")
        logger.info(f"  Deputy monthly salary: R${DEPUTY_MONTHLY_SALARY:,.0f}")
        logger.info(f"  Max savings over 8 years: R${MAX_SAVINGS_8Y:,.0f}")

        # Fetch all politicians with TSE data from the backend
        resp = requests.get(
            "http://localhost:8080/api/v1/politicians/search?name=",
            timeout=10
        )
        if resp.status_code != 200:
            logger.error(f"Failed to fetch politicians: {resp.status_code}")
            return

        politicians = resp.json()
        logger.info(f"  Found {len(politicians)} politicians")

        flagged = 0
        processed = 0

        for pol in politicians:
            a14 = pol.get("declaredAssets2014")
            a22 = pol.get("declaredAssets")
            name = pol.get("name", "Unknown")
            pol_id = pol.get("id")

            if not a14 or not a22:
                continue

            actual_growth = a22 - a14

            if actual_growth <= 0:
                anomaly_score = 0.0
            else:
                anomaly_score = round(actual_growth / MAX_SAVINGS_8Y, 2)

            # Determine severity
            if anomaly_score > 5.0:
                severity = "🔴 CRÍTICO"
            elif anomaly_score > 2.0:
                severity = "🟠 ALTO"
            elif anomaly_score > 1.0:
                severity = "🟡 ATENÇÃO"
            else:
                severity = "🟢 NORMAL"

            logger.info(
                f"  {name}: grew R${actual_growth:,.0f} | "
                f"max_salary=R${MAX_SAVINGS_8Y:,.0f} | "
                f"anomaly={anomaly_score:.2f}x | {severity}"
            )

            if anomaly_score > 1.0:
                flagged += 1

            # Use PATCH-style update via the existing ingestion endpoint
            # We need to use the SAME externalId that was used when ingesting the record
            # The other workers use "camara_{camara_id}" format
            # We can find this by looking at the politician's data - the ID in Câmara API
            # For now, use a direct DB update approach via the /ingest endpoint
            # matching by name (the backend upserts by externalId)

            # Find the Câmara API ID for this politician
            from src.core.api_client import GovAPIClient
            camara = GovAPIClient("https://dadosabertos.camara.leg.br/api/v2", request_delay=0.1)
            search_results = camara.get("deputados", params={
                "nome": name,
                "pagina": 1,
                "itens": 5,
                "ordem": "ASC",
                "ordenarPor": "nome"
            })

            if search_results and "dados" in search_results and search_results["dados"]:
                dep = search_results["dados"][0]
                external_id = f"camara_{dep['id']}"
            else:
                logger.warning(f"  Could not find Câmara ID for {name}, skipping")
                continue

            self.backend.ingest_politician({
                "externalId": external_id,
                "name": name,
                "party": pol.get("party"),
                "state": pol.get("state"),
                "position": pol.get("position", "Deputado Federal"),
                "wealthAnomaly": anomaly_score
            })
            processed += 1

        logger.info(f"=== Wealth Anomaly Complete ===")
        logger.info(f"  Processed: {processed}")
        logger.info(f"  Flagged (>1.0x salary): {flagged}")


if __name__ == "__main__":
    worker = WealthAnomalyWorker()
    worker.run()
