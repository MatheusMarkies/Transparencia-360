import logging
import traceback
import os  # Adicionado para ler as variáveis de ambiente
from typing import Dict, Any, List
from neo4j import GraphDatabase
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpatialAnomalyWorker:
    """
    Rods a cypher query on Neo4j to detect Teleportation Anomalies:
    A politician cannot be physically present in a Plenary Session in DF (Brasilia)
    AND generating an expense that requires physical presence (meal, hotel, car rental)
    in another state on the exact same day.
    """
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687", neo4j_user: str = "neo4j", neo4j_pwd: str = None):
        # Lê a senha do ambiente; se não existir, usa o padrão "admin123"
        pwd = neo4j_pwd or os.getenv("NEO4J_PASSWORD", "admin123")
        uri = os.getenv("NEO4J_URI", neo4j_uri)
        user = os.getenv("NEO4J_USER", neo4j_user)
        
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
        self.backend = BackendClient()

    def close(self):
        self.driver.close()

    def find_anomalies(self) -> Dict[str, List[Dict[str, Any]]]:
        """Runs the Cypher query and groups anomalies by politician."""
        query = """
        MATCH (p:Politico)-[:ESTEVE_PRESENTE_EM]->(s:SessaoPlenario),
              (p)-[:GEROU_DESPESA]->(d:Despesa)
        WHERE s.data = d.dataEmissao
              AND d.ufFornecedor <> 'DF'
              AND d.ufFornecedor <> 'NA'
        RETURN p.externalId AS externalId,
               p.name AS name,
               s.data AS dataSessao,
               d.categoria AS categoria,
               d.nomeFornecedor AS fornecedor,
               d.valorDocumento AS valor,
               d.ufFornecedor AS uf
        """
        anomalies_by_politician = {}
        try:
            with self.driver.session() as session:
                result = session.run(query)
                for record in result:
                    external_id = record["externalId"]
                    if external_id not in anomalies_by_politician:
                        anomalies_by_politician[external_id] = []
                    
                    anomalies_by_politician[external_id].append({
                        "data": record["dataSessao"],
                        "categoria": record["categoria"],
                        "fornecedor": record["fornecedor"],
                        "valor": record["valor"],
                        "uf": record["uf"],
                        "descricao": f"Sessão no DF e despesa presencial ({record['categoria']}) em {record['uf']} no mesmo dia."
                    })
            return anomalies_by_politician
        except Exception as e:
            logger.error(f"Error executing Neo4j query for spatial anomalies: {e}")
            logger.error(traceback.format_exc())
            return {}

    def run(self, limit: int = 100):
        logger.info("=== Spatial Anomaly Worker (Teleportation Detector) ===")
        logger.info("Step 1: Finding anomalies in Neo4j...")
        anomalies = self.find_anomalies()
        
        if not anomalies:
            logger.info("No spatial anomalies detected or Neo4j data is empty/unavailable.")
            self.close()
            return

        logger.info(f"Step 2: Sending anomalies to backend for {len(anomalies)} politicians...")
        import json
        
        count = 0
        for external_id, issues in anomalies.items():
            if count >= limit:
                break
                
            payload = {
                "externalId": external_id,
                "teleportAnomalyCount": len(issues),
                "teleportAnomalyDetails": json.dumps(issues, ensure_ascii=False)
            }
            logger.info(f"  -> Deputado {external_id} has {len(issues)} teleportation anomalies.")
            self.backend.ingest_politician(payload)
            count += 1
            
        logger.info("Spatial Anomaly Worker finished successfully.")
        self.close()

if __name__ == "__main__":
    worker = SpatialAnomalyWorker()
    parser.add_argument("--limit", type=int, default=15, help="Number of parliamentarians to process")
    args = parser.parse_args()
    worker.run(limit=args.limit)