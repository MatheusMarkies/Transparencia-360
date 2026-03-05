package com.tp360.core.repositories.neo4j;

import com.tp360.core.dto.DoacaoRiscoDTO;
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
        /**
         * NOVO GRAFO INVESTIGATIVO: Extrai as Teias de Emendas e Triangulações
         * Societárias
         */
        @Query("MATCH (p:Politico {id: $politicoId}) " +
        // 1. Caminho: Emendas -> Municipio -> Contratos (A Rota do Orçamento)
                        "OPTIONAL MATCH (p)-[r1:ENVIOU_EMENDA]->(em:Emenda)-[r2:DESTINADA_A]->(m:Municipio) " +
                        "OPTIONAL MATCH (m)-[r3:CONTRATOU]->(emp1:Empresa) " +
                        "WITH p, collect(DISTINCT em) as emendas, collect(DISTINCT m) as municipios, collect(DISTINCT emp1) as empresas1, "
                        +
                        "     collect(DISTINCT r1) as r1s, collect(DISTINCT r2) as r2s, collect(DISTINCT r3) as r3s " +

                        // 2. Caminho: Corrupção Circular (Sócios das empresas que Doaram pro Deputado)
                        "OPTIONAL MATCH (p)<-[r4:DOOU_PARA_CAMPANHA]-(socio:Pessoa)-[r5:SOCIO_DE|SOCIO_ADMINISTRADOR_DE]->(emp2:Empresa) "
                        +
                        "WITH p, emendas, municipios, empresas1, r1s, r2s, r3s, " +
                        "     collect(DISTINCT socio) as socios, collect(DISTINCT emp2) as empresas2, " +
                        "     collect(DISTINCT r4) as r4s, collect(DISTINCT r5) as r5s " +

                        // 3. Caminho: Despesas Anômalas de Gabinete (Agrupadas para não estourar o
                        // ecrã)
                        "OPTIONAL MATCH (p)-[:GEROU_DESPESA]->(d:Despesa) " +
                        "WITH p, emendas, municipios, empresas1, socios, empresas2, r1s, r2s, r3s, r4s, r5s, " +
                        "     d.nomeFornecedor AS fornecedor, sum(d.valorDocumento) AS valorTotal, count(d) AS qtdDocs "
                        +

                        "WITH p, emendas, municipios, empresas1, socios, empresas2, r1s, r2s, r3s, r4s, r5s, " +
                        "     collect(CASE WHEN fornecedor IS NOT NULL THEN { id: 'forn_' + fornecedor, labels: ['DespesaAgrupada'], properties: { nomeFornecedor: fornecedor, valorDocumento: valorTotal, qtd: qtdDocs } } END) AS nodesDespesa, "
                        +
                        "     collect(CASE WHEN fornecedor IS NOT NULL THEN { id: 'rel_' + fornecedor, source: elementId(p), target: 'forn_' + fornecedor, type: 'PAGOU_DESPESA' } END) AS relsDespesa "
                        +

                        // Consolida e junta todas as bolhas e linhas num único JSON para o React
                        "WITH [ {id: elementId(p), labels: labels(p), properties: properties(p)} ] + " +
                        "     [x IN emendas | {id: elementId(x), labels: labels(x), properties: properties(x)}] + " +
                        "     [x IN municipios | {id: elementId(x), labels: labels(x), properties: properties(x)}] + " +
                        "     [x IN (empresas1 + empresas2) | {id: elementId(x), labels: labels(x), properties: properties(x)}] + "
                        +
                        "     [x IN socios | {id: elementId(x), labels: labels(x), properties: properties(x)}] + nodesDespesa AS allNodes, "
                        +
                        "     [x IN r1s | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + "
                        +
                        "     [x IN r2s | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + "
                        +
                        "     [x IN r3s | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + "
                        +
                        "     [x IN r4s | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + "
                        +
                        "     [x IN r5s | {id: elementId(x), source: elementId(startNode(x)), target: elementId(endNode(x)), type: type(x), properties: properties(x)}] + relsDespesa AS allLinks "
                        +
                        "RETURN { nodes: allNodes, links: allLinks }")
        List<Map<String, Object>> getFullConnectionGraph(@Param("politicoId") String politicoId);

        /**
         * CORREÇÃO: Retorna explicitamente um Map JSON para evitar que o Spring Data
         * apague os campos
         */
        @Query("MATCH (p:Politico {id: $politicoId})-[:GEROU_DESPESA]->(d:Despesa) "
                        + "RETURN { id: d.id, dataEmissao: d.dataEmissao, nomeFornecedor: d.nomeFornecedor, "
                        + "categoria: d.categoria, valorDocumento: d.valorDocumento, rosieAnomalies: d.rosieAnomalies } "
                        + "ORDER BY d.dataEmissao DESC")
        List<Map<String, Object>> findDespesasMapByPoliticoId(@Param("politicoId") String politicoId);

        /**
         * CORREÇÃO: Busca seguindo o caminho correto do Grafo (Político -> Emenda ->
         * Municipio)
         */
        @Query("MATCH (p:Politico {id: $externalId})-[:ENVIOU_EMENDA]->(e:Emenda)-[:DESTINADA_A]->(m:Municipio) " +
                        "RETURN { id: e.id, ano: e.ano, valor: e.valor, tipo: e.tipo, " +
                        "         funcao: e.funcao, localidade: e.localidade, municipioIbge: m.codigoIbge } " +
                        "ORDER BY e.ano DESC, e.valor DESC")
        List<Map<String, Object>> findEmendasByPoliticoId(@Param("externalId") String externalId);

        /**
         * NOVO: Força a criação das ligações perfeitas para o Follow the Money
         */
        @Query("MATCH (p:Politico {id: $politicoId}) " +
                        "MERGE (m:Municipio {codigoIbge: $ibge}) " +
                        "MERGE (e:Emenda {id: $emendaId}) " +
                        "SET e.ano = $ano, e.valor = $valor, e.tipo = $tipo, " +
                        "    e.funcao = $funcao, e.localidade = $localidade " + // <-- NOVOS CAMPOS
                        "MERGE (p)-[:ENVIOU_EMENDA]->(e) " +
                        "MERGE (e)-[:DESTINADA_A]->(m)")
        void createEmendaRelationship(@Param("politicoId") String politicoId, @Param("ibge") String ibge,
                        @Param("emendaId") String emendaId, @Param("ano") Integer ano,
                        @Param("valor") Double valor, @Param("tipo") String tipo,
                        @Param("funcao") String funcao, @Param("localidade") String localidade);

        @Query("MATCH (p:Politico {id: $politicoId})-[:GEROU_DESPESA]->(d:Despesa) "
                        + "WITH d.nomeFornecedor AS fornecedor, SUM(d.valorDocumento) AS total "
                        + "ORDER BY total DESC LIMIT 5 "
                        + "RETURN { fornecedor: fornecedor, total: total }")
        List<Map<String, Object>> findTopFornecedoresByPoliticoId(@Param("politicoId") String politicoId);

        @Query("MATCH (p:Politico {id: $politicoId})-[:GEROU_DESPESA]->(d:Despesa) "
                        + "WITH d.categoria AS categoria, SUM(d.valorDocumento) AS total "
                        + "ORDER BY total DESC "
                        + "RETURN { categoria: categoria, total: total }")
        List<Map<String, Object>> findGastosPorCategoriaByPoliticoId(@Param("politicoId") String politicoId);

        @Query("MATCH (pol:Politico)<-[:DOOU_PARA_CAMPANHA]-(doador:Pessoa)-[:SOCIO_DE|SOCIO_ADMINISTRADOR_DE|APORTOU_CAPITAL_EM]->(empresa:Empresa) "
                        +
                        "WHERE toLower(empresa.name) CONTAINS toLower($termoEmpresa) " +
                        "RETURN pol.name AS politicoNome, doador.name AS doadorNome, doador.cpf AS doadorCpf, empresa.name AS empresaNome, empresa.cnpj AS empresaCnpj")
        List<DoacaoRiscoDTO> findDoadoresLigadosAEmpresa(@Param("termoEmpresa") String termoEmpresa);

        // Opcional: Busca por uma lista de CNPJs suspeitos (Watchlist)
        @Query("MATCH (pol:Politico)<-[:DOOU_PARA_CAMPANHA]-(doador:Pessoa)-[:SOCIO_DE|SOCIO_ADMINISTRADOR_DE|APORTOU_CAPITAL_EM]->(empresa:Empresa) "
                        +
                        "WHERE empresa.cnpj IN $cnpjsRisco " +
                        "RETURN pol.name AS politicoNome, doador.name AS doadorNome, doador.cpf AS doadorCpf, empresa.name AS empresaNome, empresa.cnpj AS empresaCnpj")
        List<DoacaoRiscoDTO> findDoacoesPorCnpjsDeRisco(@Param("cnpjsRisco") List<String> cnpjsRisco);

}