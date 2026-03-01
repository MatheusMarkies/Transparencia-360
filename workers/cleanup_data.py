import os
from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_neo4j():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "admin123")
    
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            logger.info("Cleaning Neo4j database...")
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("  ✅ Neo4j cleaned.")
    except Exception as e:
        logger.error(f"  ❌ Failed to clean Neo4j: {e}")
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    cleanup_neo4j()
