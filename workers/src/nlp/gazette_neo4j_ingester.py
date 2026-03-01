"""
Gazette Neo4j Ingester
━━━━━━━━━━━━━━━━━━━━━━
Ingere entidades extraídas de Diários Oficiais diretamente no Neo4j,
criando nós e relações que permitem queries de caminhos longos.

Modelo de dados Neo4j:
  (Licitacao {numero, modalidade, data, valor, orgao})
  (DiarioOficial {territory, date, url})
  (Empresa {cnpj, name}) 
  
  (Empresa)-[:VENCEU_LICITACAO]->(Licitacao)
  (Licitacao)-[:PUBLICADA_EM]->(DiarioOficial)
  (Politico)-[:VINCULADO_A]->(DiarioOficial)  // quando mencionado
  (Empresa)-[:MENCIONADA_EM]->(DiarioOficial)
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200


class GazetteNeo4jIngester:
    """
    Converte resultados NLP em nós e relações Neo4j.
    """

    def __init__(self, neo4j_session=None):
        self.session = neo4j_session

    def create_gazette_constraints(self, session=None):
        """Cria indexes/constraints para os nós de Diário Oficial."""
        s = session or self.session
        if not s:
            logger.warning("  ⚠️ Neo4j session não disponível")
            return
        
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:DiarioOficial) REQUIRE d.url IS UNIQUE;",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Licitacao) REQUIRE l.numero IS UNIQUE;",
            "CREATE INDEX IF NOT EXISTS FOR (d:DiarioOficial) ON (d.territory);",
            "CREATE INDEX IF NOT EXISTS FOR (l:Licitacao) ON (l.modalidade);",
        ]
        for q in queries:
            try:
                s.run(q)
            except Exception as e:
                logger.warning(f"  ⚠️ Constraint warning: {e}")
        logger.info("  ✅ Gazette constraints criados")

    def ingest_nlp_result(self, nlp_result: dict, session=None):
        """
        Ingere um resultado NLP completo no Neo4j.
        Cria: DiarioOficial, Empresa, Licitacao e suas relações.
        """
        s = session or self.session
        if not s:
            logger.warning("  ⚠️ Neo4j session não disponível. Pulando ingestão.")
            return

        url = nlp_result.get("source_url", "") or nlp_result.get("gazette_url", "")
        territory = nlp_result.get("territory", "") or nlp_result.get("gazette_territory", "")
        date = nlp_result.get("date", "") or nlp_result.get("gazette_date", "")
        entities = nlp_result.get("entities", {})

        # 1. Create DiarioOficial node
        s.run("""
            MERGE (d:DiarioOficial {url: $url})
            SET d.territory = $territory,
                d.date = $date,
                d.suspicion_score = $score
        """, url=url, territory=territory, date=date,
           score=nlp_result.get("suspicion_score", 0))

        # 2. Create Empresa nodes from CNPJs and link to DiarioOficial
        for cnpj_data in entities.get("cnpjs", []):
            cnpj = cnpj_data["cnpj"]
            company = cnpj_data.get("company_name", "")
            s.run("""
                MERGE (e:Empresa {cnpj: $cnpj})
                ON CREATE SET e.name = $company
                WITH e
                MATCH (d:DiarioOficial {url: $url})
                MERGE (e)-[:MENCIONADA_EM {context: $context}]->(d)
            """, cnpj=cnpj, company=company, url=url,
               context=cnpj_data.get("context", "")[:200])

        # 3. Create Licitacao nodes from modalidades
        for mod_data in entities.get("modalidades", []):
            modalidade = mod_data["modalidade"]
            is_dispensa = mod_data.get("is_dispensa", False)
            
            # Find associated process number
            processos = entities.get("processos", [])
            proc_numero = processos[0]["numero"] if processos else f"auto_{hash(url + modalidade) % 100000}"
            
            # Find associated value
            valores = mod_data.get("valores_nearby", [])
            valor = max(valores) if valores else 0
            
            s.run("""
                MERGE (l:Licitacao {numero: $numero})
                SET l.modalidade = $modalidade,
                    l.is_dispensa = $is_dispensa,
                    l.valor = $valor,
                    l.date = $date
                WITH l
                MATCH (d:DiarioOficial {url: $url})
                MERGE (l)-[:PUBLICADA_EM]->(d)
            """, numero=proc_numero, modalidade=modalidade,
               is_dispensa=is_dispensa, valor=valor, date=date, url=url)
            
            # Link nearby CNPJs to the Licitacao (company won/participated)
            for cnpj in mod_data.get("cnpjs_nearby", []):
                s.run("""
                    MATCH (e:Empresa {cnpj: $cnpj})
                    MATCH (l:Licitacao {numero: $numero})
                    MERGE (e)-[:VENCEU_LICITACAO {valor: $valor}]->(l)
                """, cnpj=cnpj, numero=proc_numero, valor=valor)

        # 4. Create Pessoa nodes from CPFs
        for cpf_data in entities.get("cpfs", []):
            s.run("""
                MERGE (p:Pessoa {cpf: $cpf})
                WITH p
                MATCH (d:DiarioOficial {url: $url})
                MERGE (p)-[:MENCIONADA_EM]->(d)
            """, cpf=cpf_data["cpf"], url=url)

    def ingest_batch(self, nlp_results: list[dict], session=None):
        """
        Ingere uma lista de resultados NLP no Neo4j.
        """
        s = session or self.session
        total = len(nlp_results)
        logger.info(f"  🔄 Ingerindo {total} resultados de Diários Oficiais no Neo4j...")
        
        for i, result in enumerate(nlp_results):
            self.ingest_nlp_result(result, s)
            if (i + 1) % 10 == 0:
                logger.info(f"    Progresso: {i+1}/{total}")
        
        logger.info(f"  ✅ {total} diários ingeridos no Neo4j")


class GazettePatternDetector:
    """
    Detecta padrões de fraude em licitação usando queries Cypher no Neo4j.
    """

    def __init__(self, neo4j_session=None):
        self.session = neo4j_session

    def detect_repeated_dispensas(self, session=None, min_count: int = 3) -> list[dict]:
        """
        Detecta empresas que vencem múltiplas dispensas de licitação.
        Se a empresa do parente do político ganha 10 licitações com
        'Dispensa de Licitação', é um forte indício de fraude.
        """
        s = session or self.session
        if not s:
            return []

        result = s.run("""
            MATCH (e:Empresa)-[:VENCEU_LICITACAO]->(l:Licitacao {is_dispensa: true})
            WITH e, count(l) AS dispensa_count, 
                 sum(l.valor) AS total_valor,
                 collect(l.numero) AS processos
            WHERE dispensa_count >= $min_count
            RETURN e.cnpj AS cnpj, e.name AS empresa,
                   dispensa_count, total_valor, processos
            ORDER BY dispensa_count DESC
            LIMIT 20
        """, min_count=min_count)

        findings = []
        for record in result:
            findings.append({
                "type": "DISPENSAS_REPETIDAS",
                "severity": "CRITICAL",
                "cnpj": record["cnpj"],
                "empresa": record["empresa"],
                "count": record["dispensa_count"],
                "total_valor": record["total_valor"],
                "processos": record["processos"][:10]
            })
        
        if findings:
            logger.warning(f"  🚨 {len(findings)} empresas com dispensas repetidas!")
        return findings

    def detect_politician_cnpj_link(self, politician_id: str, session=None) -> list[dict]:
        """
        Busca caminhos longos entre um político e empresas que ganharam
        licitações em Diários Oficiais:
        
        Político -> SOCIO_ADMINISTRADOR_DE -> Empresa X
        Empresa X -> VENCEU_LICITACAO -> Licitação (dispensa)
        Licitação -> PUBLICADA_EM -> DiarioOficial
        
        Ou:
        Político -> CONTRATOU -> Empresa A <- SOCIO_ADMINISTRADOR_DE <- Pessoa X
        Pessoa X -> SOCIO_ADMINISTRADOR_DE -> Empresa B -> VENCEU_LICITACAO -> Licitação
        """
        s = session or self.session
        if not s:
            return []

        # Query 1: Direct link (politician's contracted company wins bidding)
        result1 = s.run("""
            MATCH (p:Politico {id: $pol_id})-[:CONTRATOU]->(e:Empresa)-[:VENCEU_LICITACAO]->(l:Licitacao)
            RETURN p.name AS politico, e.cnpj AS cnpj, e.name AS empresa,
                   l.modalidade AS modalidade, l.valor AS valor, l.numero AS processo,
                   'DIRETO' AS grau
        """, pol_id=politician_id)

        findings = [dict(r) for r in result1]

        # Query 2: 2nd degree (politician -> employee/partner -> company -> wins bidding)
        result2 = s.run("""
            MATCH (p:Politico {id: $pol_id})-[:CONTRATOU]->(e1:Empresa)
                  <-[:SOCIO_ADMINISTRADOR_DE]-(pessoa:Pessoa)
                  -[:SOCIO_ADMINISTRADOR_DE]->(e2:Empresa)
                  -[:VENCEU_LICITACAO]->(l:Licitacao)
            WHERE e1 <> e2
            RETURN p.name AS politico, e1.cnpj AS cnpj_origem, 
                   pessoa.name AS intermediario,
                   e2.cnpj AS cnpj_destino, e2.name AS empresa_destino,
                   l.modalidade AS modalidade, l.valor AS valor,
                   '2º GRAU' AS grau
        """, pol_id=politician_id)

        findings.extend([dict(r) for r in result2])

        # Query 3: 3rd degree (full chain)
        result3 = s.run("""
            MATCH path = (p:Politico {id: $pol_id})-[*2..4]-(l:Licitacao {is_dispensa: true})
            WHERE ALL(r IN relationships(path) WHERE type(r) IN 
                  ['CONTRATOU','SOCIO_ADMINISTRADOR_DE','SOCIO_DE','VENCEU_LICITACAO','DOOU_PARA_CAMPANHA'])
            RETURN p.name AS politico,
                   [n IN nodes(path) WHERE n:Empresa | n.cnpj] AS cnpjs_no_caminho,
                   [n IN nodes(path) WHERE n:Pessoa | n.name] AS pessoas_no_caminho,
                   l.modalidade AS modalidade, l.valor AS valor,
                   length(path) AS grau_distancia
            LIMIT 10
        """, pol_id=politician_id)

        for r in result3:
            findings.append({
                "type": "CAMINHO_LONGO_DISPENSA",
                "severity": "CRITICAL",
                "politico": r["politico"],
                "cnpjs": r["cnpjs_no_caminho"],
                "pessoas": r["pessoas_no_caminho"],
                "modalidade": r["modalidade"],
                "valor": r["valor"],
                "grau": f"{r['grau_distancia']}º GRAU"
            })

        if findings:
            logger.warning(f"  🚨 {len(findings)} conexões político-licitação encontradas!")
        return findings

    def detect_concentrated_municipalities(self, session=None, min_count: int = 3) -> list[dict]:
        """
        Detecta empresas que vencem licitações concentradas em poucos municípios.
        """
        s = session or self.session
        if not s:
            return []

        result = s.run("""
            MATCH (e:Empresa)-[:VENCEU_LICITACAO]->(l:Licitacao)
                  -[:PUBLICADA_EM]->(d:DiarioOficial)
            WITH e, d.territory AS municipio, count(l) AS licitacoes,
                 sum(l.valor) AS total
            WITH e, collect({municipio: municipio, licitacoes: licitacoes, total: total}) AS municipios
            WHERE size(municipios) <= 2 AND 
                  REDUCE(s = 0, m IN municipios | s + m.licitacoes) >= $min_count
            RETURN e.cnpj AS cnpj, e.name AS empresa, municipios
            ORDER BY REDUCE(s = 0, m IN municipios | s + m.licitacoes) DESC
            LIMIT 10
        """, min_count=min_count)

        return [dict(r) for r in result]

    def full_gazette_analysis(self, politician_id: str, session=None) -> dict:
        """
        Análise completa de Diários Oficiais para um político.
        """
        s = session or self.session
        
        repeated = self.detect_repeated_dispensas(s)
        pol_links = self.detect_politician_cnpj_link(politician_id, s)
        concentrated = self.detect_concentrated_municipalities(s)
        
        return {
            "repeated_dispensas": repeated,
            "politician_gazette_links": pol_links,
            "concentrated_municipalities": concentrated,
            "total_alerts": len(repeated) + len(pol_links) + len(concentrated)
        }


if __name__ == "__main__":
    logger.info("=== Gazette Neo4j Ingester + Pattern Detector ===")
    logger.info("  Para usar, inicialize com uma sessão Neo4j:")
    logger.info("  ingester = GazetteNeo4jIngester(neo4j_session)")
    logger.info("  detector = GazettePatternDetector(neo4j_session)")
