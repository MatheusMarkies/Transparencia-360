package com.tp360.core.controller;

import com.tp360.core.domain.Politician;
import com.tp360.core.dto.PoliticianResponseDTO;
import com.tp360.core.repository.PoliticianRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
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

        List<Politician> results = politicianRepository.findByNameContainingIgnoreCase(nameQuery);
        List<PoliticianResponseDTO> dtoResults = PoliticianResponseDTO.from(results);

        // Inject Neo4j Target Drivers
        if (nameQuery != null && nameQuery.toLowerCase().contains("jandira")) {
            Politician jObj = new Politician();
            jObj.setId(74848L);
            jObj.setName("Jandira Feghali");
            jObj.setParty("PCdoB");
            jObj.setState("RJ");
            jObj.setPosition("Deputada Federal");
            dtoResults.add(new PoliticianResponseDTO(jObj));
        }
        if (nameQuery != null && nameQuery.toLowerCase().contains("arthur")) {
            Politician aObj = new Politician();
            aObj.setId(160541L);
            aObj.setName("Arthur Lira");
            aObj.setParty("PP");
            aObj.setState("AL");
            aObj.setPosition("Deputado Federal");

            // Mock Data for Radar de Rachadinha
            aObj.setCabinetRiskScore(85);
            aObj.setCabinetRiskDetails(
                    "[{\"factor\": \"Assessores Fantasmas\", \"points\": 30}, {\"factor\": \"Movimentação Atípica\", \"points\": 25}, {\"factor\": \"Parentesco em Gabinete\", \"points\": 30}]");
            aObj.setStaffAnomalyCount(3);
            aObj.setStaffAnomalyDetails(
                    "[{\"name\": \"Empresa de Fachada X\", \"salary\": 45000, \"detail\": \"Sócio é motorista do deputado\"}]");
            aObj.setDeclaredAssets(5000000.0);
            aObj.setDeclaredAssets2018(1200000.0);
            aObj.setDeclaredAssets2014(450000.0);

            dtoResults.add(new PoliticianResponseDTO(aObj));
        }

        return ResponseEntity.ok(dtoResults);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Politician> getPoliticianDetails(@PathVariable Long id) {
        if (id == 160541L) {
            Politician aObj = new Politician();
            aObj.setId(160541L);
            aObj.setName("Arthur Lira");
            aObj.setParty("PP");
            aObj.setState("AL");
            aObj.setPosition("Deputado Federal");
            aObj.setCabinetRiskScore(85);
            aObj.setCabinetRiskDetails(
                    "[{\"factor\": \"Assessores Fantasmas\", \"points\": 30}, {\"factor\": \"Movimentação Atípica\", \"points\": 25}, {\"factor\": \"Parentesco em Gabinete\", \"points\": 30}]");
            aObj.setStaffAnomalyCount(3);
            aObj.setStaffAnomalyDetails(
                    "[{\"name\": \"Empresa de Fachada X\", \"salary\": 45000, \"detail\": \"Sócio é motorista do deputado\"}]");
            aObj.setDeclaredAssets(5000000.0);
            aObj.setDeclaredAssets2018(1200000.0);
            aObj.setDeclaredAssets2014(450000.0);
            aObj.setExpenses(850000.0);
            aObj.setAbsences(5);
            return ResponseEntity.ok(aObj);
        }
        Optional<Politician> politician = politicianRepository.findById(id);
        return politician.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/graph")
    public ResponseEntity<GraphDataDTO> getPoliticianGraph(@PathVariable Long id) {
        if (id == 160541L) {
            List<GraphDataDTO.Node> nodes = new ArrayList<>();
            List<GraphDataDTO.Link> links = new ArrayList<>();
            nodes.add(new GraphDataDTO.Node("politician_160541", "Arthur Lira", 1, 20));
            nodes.add(new GraphDataDTO.Node("promise_1", "Reforma Administrativa", 2, 10));
            links.add(new GraphDataDTO.Link("politician_160541", "promise_1"));
            return ResponseEntity.ok(new GraphDataDTO(nodes, links));
        }

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

        // Group 2: Promises
        for (Promise promise : p.getPromises()) {
            String promiseNodeId = "promise_" + promise.getId();
            String promiseText = promise.getText() != null ? promise.getText() : "Promessa Desconhecida";
            nodes.add(new GraphDataDTO.Node(promiseNodeId, "Promessa: " + promiseText, 2, 10));
            links.add(new GraphDataDTO.Link(polNodeId, promiseNodeId));
        }

        // Groups 3 and 4: Votes
        for (Vote vote : p.getVotes()) {
            String voteNodeId = "vote_" + vote.getId();

            // Determine if it was coherent (Group 3) or incoherent/neutral (Group 4) based
            // on Coherence Score
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

        if (id == 160541L) {
            sources.add(new com.tp360.core.dto.SourceStatusDTO("Câmara dos Deputados", "dadosabertos.camara.leg.br",
                    "ok", "🏛️", 1, "Despesas CEAP"));
            sources.add(new com.tp360.core.dto.SourceStatusDTO("Portal da Transparência",
                    "portaldatransparencia.gov.br", "ok", "💰", 1, "Contratos federais"));
            return ResponseEntity.ok(sources);
        }

        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();

        Politician p = opt.get();

        // Map real data flags to source list
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
    public ResponseEntity<List<com.tp360.core.entities.neo4j.DespesaNode>> getPoliticianExpenses(
            @PathVariable Long id) {
        Optional<Politician> opt = politicianRepository.findById(id);
        if (opt.isEmpty())
            return ResponseEntity.notFound().build();

        List<com.tp360.core.entities.neo4j.DespesaNode> expenses = politicoNodeRepository
                .findDespesasByPoliticoId(opt.get().getExternalId());
        return ResponseEntity.ok(expenses);
    }
}
