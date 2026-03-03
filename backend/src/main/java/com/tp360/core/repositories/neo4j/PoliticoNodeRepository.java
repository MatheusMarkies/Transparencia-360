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
         * UPDATED: Agrega as despesas por Fornecedor (Super Bolhas) e mantém o fluxo
         * das Emendas.
         */
        @Query("MATCH (p:Politico {id: $politicoId}) " +
                        "OPTIONAL MATCH (p)-[r1:ENVIOU_EMENDA]->(m:Municipio) " +
                        "OPTIONAL MATCH (m)-[r2:CONTRATOU]->(e:Empresa) " +
                        "WITH p, collect(DISTINCT m) AS municipios, collect(DISTINCT e) AS empresas, collect(DISTINCT r1) AS rels1, collect(DISTINCT r2) AS rels2 "
                        +

                        // Agrupamento Mágico: Junta todas as NFs do mesmo fornecedor numa única linha
                        "OPTIONAL MATCH (p)-[:GEROU_DESPESA]->(d:Despesa) " +
                        "WITH p, municipios, empresas, rels1, rels2, d.nomeFornecedor AS fornecedor, head(collect(d.categoria)) AS categoria, sum(d.valorDocumento) AS valorTotal, count(d) AS qtdDocs "
                        +
                        "WHERE fornecedor IS NOT NULL " +

                        // Cria os "Super Nós" virtuais na memória do Neo4j para mandar pro Frontend
                        "WITH p, municipios, empresas, rels1, rels2, " +
                        "     collect({ id: 'forn_' + fornecedor, labels: ['DespesaAgrupada'], properties: { nomeFornecedor: fornecedor, categoria: categoria, valorDocumento: valorTotal, qtd: qtdDocs } }) AS nodesDespesa, "
                        +
                        "     collect({ id: 'rel_' + fornecedor, source: elementId(p), target: 'forn_' + fornecedor, type: 'TOTAL_PAGO' }) AS relsDespesa "
                        +

                        "WITH [ {id: elementId(p), labels: labels(p), properties: properties(p)} ] + " +
                        "     [x IN municipios WHERE x IS NOT NULL | {id: elementId(x), labels: labels(x), properties: properties(x)}] + "
                        +
                        "     [x IN empresas WHERE x IS NOT NULL | {id: elementId(x), labels: labels(x), properties: properties(x)}] + nodesDespesa AS allNodes, "
                        +
                        "     [x IN rels1 WHERE x IS NOT NULL | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + "
                        +
                        "     [x IN rels2 WHERE x IS NOT NULL | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + relsDespesa AS allLinks "
                        +
                        "RETURN { nodes: allNodes, links: allLinks }")
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