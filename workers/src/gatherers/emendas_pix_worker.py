import logging
import json
from neo4j import GraphDatabase
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmendasPixWorker:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.backend = BackendClient()

    def close(self):
        self.driver.close()

    def run(self):
        """
        Executes the Cypher Query to detect the circular Emendas Pix anomaly:
        (Politico)-[:ENVIOU_EMENDA]->(Municipio)-[:CONTRATOU]->(Empresa)<-[:SOCIO_DE]-(Pessoa)-[:DOOU_PARA_CAMPANHA]->(Politico)

        When a match is found, formats the anomaly and sends to Backend via standard ingest_politician update.
        """
        logger.info("Starting Emendas Pix Rules Engine (Circular Flow Anomaly Detector)...")
        
        # We are looking for any cycles for any politician. 
        # Using 2nd degree expansion as decided: The Contractor Company has a Partner who was a Campaign Donor to the same Politician.
        cypher_query = """
        MATCH 
          (p:Politico)-[emenda:ENVIOU_EMENDA]->(m:Municipio),
          (m)-[contrato:CONTRATOU]->(e_contratada:Empresa),
          (socio:Pessoa)-[:SOCIO_DE]->(e_contratada),
          (socio)-[:DOOU_PARA_CAMPANHA]->(p)
        RETURN 
          p.id AS pol_id, p.name AS pol_name,
          m.name AS municipio_name, m.codigoIbge AS ibge,
          e_contratada.cnpj AS cnpj, e_contratada.name AS empresa_name,
          socio.cpf AS cpf, socio.name AS socio_name
        """
        
        anomalies_by_politician = {}

        with self.driver.session() as session:
            result = session.run(cypher_query)
            for record in result:
                pol_id = record["pol_id"]
                if pol_id not in anomalies_by_politician:
                    anomalies_by_politician[pol_id] = []
                
                anomaly_detail = {
                    "municipioIbge": record.get("ibge", "Unknown"),
                    "empresaContratada": record.get("empresa_name", record.get("cnpj", "Unknown")),
                    "socioOculto": record.get("socio_name", record.get("cpf", "Unknown"))
                }
                anomalies_by_politician[pol_id].append(anomaly_detail)
        
        if not anomalies_by_politician:
            logger.info("No Emendas Pix circular flow anomalies detected.")
            return

        for pol_id, details_list in anomalies_by_politician.items():
            logger.warning(f"CRITICAL ANOMALY: Politician {pol_id} has {len(details_list)} Emendas Pix loops.")
            payload = {
                "externalId": pol_id,
                "emendasPixAnomalyCount": len(details_list),
                "emendasPixAnomalyDetails": json.dumps(details_list)
            }
            res = self.backend.ingest_politician(payload)
            if res:
                logger.info(f"Successfully flagged Politician {pol_id} for Emendas Pix Anomaly.")
            else:
                logger.error(f"Failed to flag Politician {pol_id}.")

        logger.info("Finished Emendas Pix Rules Engine.")
