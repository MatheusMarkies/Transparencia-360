package com.tp360.core.controller;

import com.tp360.core.domain.Politician;
import com.tp360.core.dto.PoliticianResponseDTO;
import com.tp360.core.repository.PoliticianRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import com.tp360.core.domain.Promise;
import com.tp360.core.domain.Vote;
import com.tp360.core.dto.DoacaoRiscoDTO;
import com.tp360.core.dto.GraphDataDTO;

@RestController
@RequestMapping("/api/v1/politicians")
@CrossOrigin(origins = { "http://localhost:5173", "http://localhost:5174", "http://localhost:3000" })
public class FrontendSearchController {

    private final PoliticianRepository politicianRepository;
    private final com.tp360.core.repositories.neo4j.PoliticoNodeRepository politicoNodeRepository;
    private final com.tp360.core.service.DataIngestionService dataIngestionService;

    public FrontendSearchController(PoliticianRepository politicianRepository,
            com.tp360.core.repositories.neo4j.PoliticoNodeRepository politicoNodeRepository,
            com.tp360.core.service.DataIngestionService dataIngestionService) {
        this.politicianRepository = politicianRepository;
        this.politicoNodeRepository = politicoNodeRepository;
        this.dataIngestionService = dataIngestionService;
    }

    @GetMapping("/search")
    public ResponseEntity<List<PoliticianResponseDTO>> searchPoliticians(
            @RequestParam(name = "name") String nameQuery) {
        // Busca puramente do banco de dados relacional
        List<Politician> results = politicianRepository.findByNameContainingIgnoreCase(nameQuery);
        List<PoliticianResponseDTO> dtoResults = PoliticianResponseDTO.from(results);
        return ResponseEntity.ok(dtoResults);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Politician> getPoliticianDetails(@PathVariable Long id) {
        // Retorna apenas se existir no Postgres
        Optional<Politician> politician = politicianRepository.findById(id);
        return politician.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/external/{externalId}")
    public ResponseEntity<Politician> getPoliticianByExternalId(@PathVariable String externalId) {
        Optional<Politician> politician = politicianRepository.findByExternalId(externalId);
        return politician.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<Politician> updatePolitician(@RequestBody Politician politician) {
        Politician saved = dataIngestionService.ingestPolitician(politician);
        return ResponseEntity.ok(saved);
    }

    @GetMapping("/{id}/graph")
    public ResponseEntity<GraphDataDTO> getPoliticianGraph(@PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        Politician p = opt.get();
        List<GraphDataDTO.Node> nodes = new ArrayList<>();
        List<GraphDataDTO.Link> links = new ArrayList<>();

        // Group 1: The Politician (Central Node)
        String polNodeId = "politician_" + p.getId();
        nodes.add(new GraphDataDTO.Node(polNodeId, p.getName(), 1, 20));

        // Group 2: Promises (Reais extraídas do banco)
        for (Promise promise : p.getPromises()) {
            String promiseNodeId = "promise_" + promise.getId();
            String promiseText = promise.getText() != null ? promise.getText() : "Promessa Desconhecida";
            nodes.add(new GraphDataDTO.Node(promiseNodeId, "Promessa: " + promiseText, 2, 10));
            links.add(new GraphDataDTO.Link(polNodeId, promiseNodeId));
        }

        // Groups 3 and 4: Votes (Reais extraídos do banco)
        for (Vote vote : p.getVotes()) {
            String voteNodeId = "vote_" + vote.getId();
            boolean isCoherent = vote.getCoherenceScore() != null && vote.getCoherenceScore() > 0;
            int group = isCoherent ? 3 : 4;

            String voteChoice = vote.getVoteChoice() != null ? vote.getVoteChoice() : "Não Votou";
            String propSummary = vote.getPropositionSummary() != null ? vote.getPropositionSummary()
                    : "Proposição " + vote.getPropositionExternalId();
            String nodeName = "Votou " + voteChoice + " em: " + propSummary;

            nodes.add(new GraphDataDTO.Node(voteNodeId, nodeName, group, 5));
            links.add(new GraphDataDTO.Link(polNodeId, voteNodeId));
        }

        GraphDataDTO graphData = new GraphDataDTO(nodes, links);
        return ResponseEntity.ok(graphData);
    }

    @GetMapping("/{id}/sources")
    public ResponseEntity<List<com.tp360.core.dto.SourceStatusDTO>> getPoliticianSources(@PathVariable Long id) {
        List<com.tp360.core.dto.SourceStatusDTO> sources = new ArrayList<>();

        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();

        Politician p = opt.get();

        // Mapeamento real de fontes baseado nos dados existentes do político
        sources.add(new com.tp360.core.dto.SourceStatusDTO(
                "Câmara dos Deputados", "dadosabertos.camara.leg.br", "ok", "🏛️",
                p.getExpenses() != null ? 1 : 0, "Despesas CEAP, presenças e votações"));

        sources.add(new com.tp360.core.dto.SourceStatusDTO(
                "Portal da Transparência", "portaldatransparencia.gov.br", "ok", "💰",
                (p.getPropositions() != null ? 1 : 0), "Contratos federais e remuneração"));

        sources.add(new com.tp360.core.dto.SourceStatusDTO(
                "Querido Diário (OKBR)", "queridodiario.ok.org.br", "ok", "📰",
                p.getNlpGazetteCount() != null ? p.getNlpGazetteCount() : 0, "Menções em Diários Oficiais"));

        sources.add(new com.tp360.core.dto.SourceStatusDTO(
                "TSE - Dados Eleitorais", "dadosabertos.tse.jus.br", "ok", "🗳️",
                p.getDeclaredAssets() != null ? 1 : 0, "Doações de campanha e patrimônio"));

        sources.add(new com.tp360.core.dto.SourceStatusDTO(
                "DataJud (CNJ)", "datajud.cnj.jus.br", "ok", "⚖️",
                p.getJudicialRiskScore() != null ? 1 : 0, "Processos de improbidade"));

        return ResponseEntity.ok(sources);
    }

    @GetMapping("/{id}/expenses")
    public ResponseEntity<List<Map<String, Object>>> getPoliticianExpenses(@PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();

        // Agora pede a lista no formato de Map seguro!
        List<Map<String, Object>> expenses = politicoNodeRepository
                .findDespesasMapByPoliticoId(opt.get().getExternalId());
        return ResponseEntity.ok(expenses);
    }

    @GetMapping("/{id}/emendas")
    public ResponseEntity<List<Map<String, Object>>> getPoliticianEmendas(@PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();

        List<Map<String, Object>> emendas = politicoNodeRepository.findEmendasByPoliticoId(opt.get().getExternalId());
        return ResponseEntity.ok(emendas);
    }

    @GetMapping("/{id}/top-fornecedores")
    public ResponseEntity<List<Map<String, Object>>> getTopFornecedores(@PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();
        return ResponseEntity.ok(politicoNodeRepository.findTopFornecedoresByPoliticoId(opt.get().getExternalId()));
    }

    @GetMapping("/{id}/gastos-categoria")
    public ResponseEntity<List<Map<String, Object>>> getGastosCategoria(@PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();
        return ResponseEntity.ok(politicoNodeRepository.findGastosPorCategoriaByPoliticoId(opt.get().getExternalId()));
    }

    @GetMapping("/{id}/rosie-anomalies")
    public ResponseEntity<Map<String, Object>> getRosieAnomalies(@PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();

        Politician p = opt.get();
        // Extract the numeric deputy ID from externalId (e.g., "camara_204379" ->
        // "204379")
        String externalId = p.getExternalId();
        String deputyNumericId = externalId != null && externalId.contains("_")
                ? externalId.substring(externalId.lastIndexOf("_") + 1)
                : externalId;

        // Search for the Rosie report file on disk
        java.nio.file.Path reportsDir = java.nio.file.Paths.get(System.getProperty("user.dir"))
                .resolve("data").resolve("processed").resolve("rosie_reports");

        Map<String, Object> anomalyMap = new java.util.HashMap<>();

        if (!java.nio.file.Files.isDirectory(reportsDir)) {
            return ResponseEntity.ok(anomalyMap);
        }

        try {
            // Find the report file matching this deputy ID
            java.util.Optional<java.nio.file.Path> reportFile = java.nio.file.Files.list(reportsDir)
                    .filter(path -> path.getFileName().toString().endsWith("_" + deputyNumericId + ".json"))
                    .findFirst();

            if (reportFile.isEmpty()) {
                return ResponseEntity.ok(anomalyMap);
            }

            String content = java.nio.file.Files.readString(reportFile.get(), java.nio.charset.StandardCharsets.UTF_8);
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            Map<String, Object> report = mapper.readValue(content,
                    new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
                    });

            // Build receipt_id -> list of anomalies map
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> allAnomalies = (List<Map<String, Object>>) report
                    .get("todas_anomalias_detalhadas");
            if (allAnomalies != null) {
                for (Map<String, Object> anomaly : allAnomalies) {
                    String receiptId = (String) anomaly.get("receipt_id");
                    if (receiptId != null) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> list = (List<Map<String, Object>>) anomalyMap
                                .computeIfAbsent(receiptId, k -> new ArrayList<>());
                        Map<String, Object> entry = new java.util.HashMap<>();
                        entry.put("classifier", anomaly.get("classifier"));
                        entry.put("reason", anomaly.get("reason"));
                        entry.put("confidence", anomaly.get("confidence"));
                        list.add(entry);
                    }
                }
            }

            return ResponseEntity.ok(anomalyMap);
        } catch (Exception e) {
            return ResponseEntity.ok(anomalyMap);
        }
    }

    @GetMapping("/doacoes-risco")
    public List<DoacaoRiscoDTO> rastrearDoacoesPorEmpresa(@RequestParam String nomeEmpresa) {
        // Exemplo de uso: GET /api/v1/investigacao/doacoes-risco?nomeEmpresa=BANCO
        // MASTER
        return politicoNodeRepository.findDoadoresLigadosAEmpresa(nomeEmpresa);
    }
}