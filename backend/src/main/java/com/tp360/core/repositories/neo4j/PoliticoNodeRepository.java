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
         */
        @Query("MATCH path = (p:Politico)-[:CONTRATOU]->(e1:Empresa)<-[:SOCIO_ADMINISTRADOR_DE|SOCIO_DE]-(s:Pessoa)-[:SOCIO_ADMINISTRADOR_DE|SOCIO_DE]->(e2:Empresa)<-[:APORTOU_CAPITAL_EM]-(d:Pessoa)-[:DOOU_PARA_CAMPANHA]->(p) "
                        + "WHERE p.id = $politicoId "
                        + "UNWIND nodes(path) AS n "
                        + "UNWIND relationships(path) AS r "
                        + "RETURN { nodes: collect(DISTINCT { id: elementId(n), labels: labels(n), properties: properties(n) }), links: collect(DISTINCT { id: elementId(r), source: elementId(startNode(r)), target: elementId(endNode(r)), type: type(r), properties: properties(r) }) }")
        List<Map<String, Object>> findTriangulationPath(@Param("politicoId") String politicoId);

        /**
         * Simple node extraction just to build the D3/Force graph in the frontend.
         */
        @Query("MATCH path = (p:Politico)-[*1..3]-(connected) "
                        + "WHERE p.id = $politicoId "
                        + "UNWIND nodes(path) AS n "
                        + "UNWIND relationships(path) AS r "
                        + "RETURN { nodes: collect(DISTINCT { id: elementId(n), labels: labels(n), properties: properties(n) }), links: collect(DISTINCT { id: elementId(r), source: elementId(startNode(r)), target: elementId(endNode(r)), type: type(r), properties: properties(r) }) }")
        List<Map<String, Object>> getFullConnectionGraph(@Param("politicoId") String politicoId);

        /**
         * CORREÇÃO: Usando LIMIT 15 para não travar o backend e WHERE p.id explícito
         */
        @Query("MATCH (p:Politico)-[:GEROU_DESPESA]->(d:Despesa) "
                        + "WHERE p.id = $politicoId "
                        + "RETURN d ORDER BY d.dataEmissao DESC LIMIT 15")
        List<com.tp360.core.entities.neo4j.DespesaNode> findDespesasByPoliticoId(
                        @Param("politicoId") String politicoId);

}