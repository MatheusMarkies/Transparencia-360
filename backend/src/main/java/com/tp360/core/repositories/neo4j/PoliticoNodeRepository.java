package com.tp360.core.repositories.neo4j;

import com.tp360.core.entities.neo4j.PoliticoNode;
import org.springframework.data.neo4j.repository.Neo4jRepository;
import org.springframework.data.neo4j.repository.query.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;

@Repository
public interface PoliticoNodeRepository extends Neo4jRepository<PoliticoNode, String> {

        /**
         * Executes the heavy 3rd-degree triangulation query.
         * Looks for: Politician -> (contracts) -> Company 1 <- (partner) <- Person 1 ->
         * (partner) -> Company 2 <- (donor) <- Person 2 -> (donates) -> Politician
         */
        @Query("MATCH path = (p:Politico {id: $politicoId})-[:CONTRATOU]->(e1:Empresa)<-[:SOCIO_ADMINISTRADOR_DE|SOCIO_DE]-(s:Pessoa)-[:SOCIO_ADMINISTRADOR_DE|SOCIO_DE]->(e2:Empresa)<-[:APORTOU_CAPITAL_EM]-(d:Pessoa)-[:DOOU_PARA_CAMPANHA]->(p) "
                        + "UNWIND nodes(path) AS n "
                        + "UNWIND relationships(path) AS r "
                        + "RETURN { nodes: collect(DISTINCT { id: elementId(n), labels: labels(n), properties: properties(n) }), links: collect(DISTINCT { id: elementId(r), source: elementId(startNode(r)), target: elementId(endNode(r)), type: type(r), properties: properties(r) }) }")
        List<Map<String, Object>> findTriangulationPath(@Param("politicoId") String politicoId);

        /**
         * Simple node extraction just to build the D3/Force graph in the frontend.
         * Returns all nodes connected up to 4 hops away from the Politician.
         */
        @Query("MATCH path = (p:Politico {id: $politicoId})-[*1..3]-(connected) "
                        + "UNWIND nodes(path) AS n "
                        + "UNWIND relationships(path) AS r "
                        + "RETURN { nodes: collect(DISTINCT { id: elementId(n), labels: labels(n), properties: properties(n) }), links: collect(DISTINCT { id: elementId(r), source: elementId(startNode(r)), target: elementId(endNode(r)), type: type(r), properties: properties(r) }) }")
        List<Map<String, Object>> getFullConnectionGraph(@Param("politicoId") String politicoId);

        @Query("MATCH (p:Politico {id: $politicoId})-[:GEROU_DESPESA]->(d:Despesa) RETURN d ORDER BY d.dataEmissao DESC")
        List<com.tp360.core.entities.neo4j.DespesaNode> findDespesasByPoliticoId(
                        @Param("politicoId") String politicoId);

}
