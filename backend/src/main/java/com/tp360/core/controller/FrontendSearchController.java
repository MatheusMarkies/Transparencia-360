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
import com.tp360.core.dto.GraphDataDTO;

@RestController
@RequestMapping("/api/v1/politicians")
@CrossOrigin(origins = { "http://localhost:5173", "http://localhost:5174", "http://localhost:3000" })
public class FrontendSearchController {

    private final PoliticianRepository politicianRepository;
    private final com.tp360.core.repositories.neo4j.PoliticoNodeRepository politicoNodeRepository;

    public FrontendSearchController(PoliticianRepository politicianRepository,
            com.tp360.core.repositories.neo4j.PoliticoNodeRepository politicoNodeRepository) {
        this.politicianRepository = politicianRepository;
        this.politicoNodeRepository = politicoNodeRepository;
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
}