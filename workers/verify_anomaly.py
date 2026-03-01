import sys
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    from src.gatherers.camara_gatherer import CamaraGatherer
    from src.gatherers.absences_worker import AbsencesWorker
    from src.gatherers.expenses_worker import ExpensesWorker
    from src.gatherers.spatial_anomaly_worker import SpatialAnomalyWorker

    logger.info("Initializing Deputy Data...")
    g = CamaraGatherer()
    g.fetch_and_ingest_deputies(page=1, fetch_items=1)

    logger.info("Extracting Absences (Sessions)...")
    # Year 2024 has more real plenary data
    w1 = AbsencesWorker(year=2024)
    w1.run(limit=1)
    
    logger.info("Extracting Expenses...")
    w2 = ExpensesWorker(year=2024)
    w2.run(limit=1)
    
    logger.info("Sleeping for 5 seconds to ensure Neo4j indexing..")
    time.sleep(5)
    
    logger.info("Running Spatial Anomaly Worker...")
    w3 = SpatialAnomalyWorker()
    w3.run(limit=10)
    
    logger.info("Test finished.")

if __name__ == "__main__":
    main()
