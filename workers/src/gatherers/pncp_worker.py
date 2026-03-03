import os
import logging
import time
import requests
import argparse
from neo4j import GraphDatabase
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PNCPWorker:
    def __init__(self):
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "admin123")
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        self.backend = BackendClient()
        
        self.headers = {"accept": "application/json"}
        # Pega a chave da API do Portal da Transparência do seu ambiente
        self.portal_key = os.getenv("PORTAL_API_KEY", "")
        if self.portal_key:
            self.headers["chave-api-dados"] = self.portal_key

    def get_target_municipalities(self, limit=10):
        """Consulta o Neo4j para descobrir quais cidades receberam emendas recentemente."""
        query = f"""
        MATCH (p:Politico)-[:ENVIOU_EMENDA]->(m:Municipio)
        RETURN DISTINCT m.codigoIbge AS ibge
        LIMIT {limit}
        """
        targets = []
        try:
            with self.driver.session() as session:
                result = session.run(query)
                for record in result:
                    targets.append(record["ibge"])
        except Exception as e:
            logger.error(f"Erro ao ler Grafo: {e}")
        return targets

    def fetch_contracts_for_municipality(ibge: str):
        """Busca contratos da cidade usando a API do Governo."""
        # ⚠️ CORREÇÃO: A API do Governo não aceita intervalos maiores que 30 dias!
        # Mudamos para buscar apenas um mês específico (ex: Janeiro de 2024).
        # Para produção real, o ideal é fazer um loop percorrendo mês a mês.
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/contratos?dataInicial=01/01/2024&dataFinal=31/01/2024&codigoMunicipioIbge={ibge}&pagina=1"
        try:
            # verify=False contorna os problemas crônicos de certificado SSL do governo BR
            response = requests.get(url, headers=self.headers, verify=False, timeout=20)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                # O log agora vai cuspir o texto exato do erro do Governo para podermos auditar
                logger.error(f"  ❌ Erro 400 para IBGE {ibge}. Motivo do Governo: {response.text}")
            elif response.status_code == 403:
                logger.error("  ❌ Acesso Negado (403) - Verifique sua PORTAL_API_KEY")
            else:
                logger.warning(f"  ⚠️ HTTP {response.status_code} para IBGE {ibge}")
        except Exception as e:
            logger.error(f"  ❌ Falha de conexão com Portal da Transparência: {e}")
        return []

    def run(self, limit=10):
        logger.info("=== PNCP/Contratos Worker - Follow The Money ===")
        
        ibges = self.get_target_municipalities(limit)
        logger.info(f"  🔍 Encontrados {len(ibges)} municípios alvo de emendas no Grafo.")

        total_contratos = 0
        for ibge in ibges:
            if not ibge or len(str(ibge)) < 5: 
                continue

            logger.info(f"    -> Rastreando contratos públicos para Município (IBGE: {ibge})...")
            contracts = self.fetch_contracts_for_municipality(ibge)
            
            for c in contracts:
                fornecedor = c.get("fornecedor", {})
                cnpj = fornecedor.get("cpfCnpj")
                nome_empresa = fornecedor.get("nome")
                
                # Se for empresa e não pessoa física/órgão
                if cnpj and len(cnpj) > 11 and nome_empresa:
                    cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
                    
                    # 🚀 MAGIA ACONTECENDO AQUI: Envia para o Java, que liga o Municipio à Empresa no Neo4j!
                    self.backend.ingest_contrato_municipal(ibge, cnpj_clean, nome_empresa)
                    total_contratos += 1
            
            time.sleep(1) # Respeitar rate limit da API do governo

        logger.info(f"  ✅ {total_contratos} novos contratos ligados a municípios com emendas!")
        logger.info("=== PNCP Worker Concluído ===")
        self.driver.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    PNCPWorker().run(limit=args.limit)