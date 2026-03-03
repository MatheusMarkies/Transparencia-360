package com.tp360.core.controller;

import com.tp360.core.domain.Politician;
import com.tp360.core.domain.Promise;
import com.tp360.core.domain.Vote;
import com.tp360.core.service.DataIngestionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/internal/workers/ingest")
public class WorkerIntegrationController {

    private final DataIngestionService dataIngestionService;

    public WorkerIntegrationController(DataIngestionService dataIngestionService) {
        this.dataIngestionService = dataIngestionService;
    }

    @PostMapping("/politician")
    public ResponseEntity<Politician> ingestPolitician(@RequestBody Politician politician) {
        Politician saved = dataIngestionService.ingestPolitician(politician);
        return ResponseEntity.ok(saved);
    }

    @PostMapping("/politician/{externalId}/promise")
    public ResponseEntity<Promise> ingestPromise(@PathVariable String externalId, @RequestBody Promise promise) {
        Promise saved = dataIngestionService.ingestPromise(externalId, promise);
        return ResponseEntity.ok(saved);
    }

    @PostMapping("/politician/{externalId}/vote")
    public ResponseEntity<Vote> ingestVote(@PathVariable String externalId, @RequestBody Vote vote) {
        Vote saved = dataIngestionService.ingestVote(externalId, vote);
        return ResponseEntity.ok(saved);
    }

    @PostMapping("/deduplicate")
    public ResponseEntity<String> deduplicatePoliticians() {
        int removed = dataIngestionService.deduplicatePoliticians();
        return ResponseEntity.ok("Removed " + removed + " duplicate politicians");
    }

    @PostMapping("/politician/{externalId}/sessao")
    public ResponseEntity<com.tp360.core.entities.neo4j.SessaoPlenarioNode> ingestSessaoPlenario(
            @PathVariable String externalId,
            @RequestBody com.tp360.core.entities.neo4j.SessaoPlenarioNode sessao) {
        dataIngestionService.ingestSessaoPlenario(externalId, sessao);
        return ResponseEntity.ok(sessao);
    }

    @PostMapping("/politician/{externalId}/despesa")
    public ResponseEntity<com.tp360.core.entities.neo4j.DespesaNode> ingestDespesa(
            @PathVariable String externalId,
            @RequestBody com.tp360.core.entities.neo4j.DespesaNode despesa) {
        dataIngestionService.ingestDespesa(externalId, despesa);
        return ResponseEntity.ok(despesa);
    }

    // --- Emendas Pix Anomaly (Circular Graph) Endpoints ---

    @PostMapping("/politician/{externalId}/emenda_pix/{municipioIbge}")
    public ResponseEntity<com.tp360.core.entities.neo4j.EmendaNode> ingestEmendaPix(
            @PathVariable String externalId,
            @PathVariable String municipioIbge,
            @RequestBody com.tp360.core.entities.neo4j.EmendaNode emenda) {
        dataIngestionService.ingestEmendaPix(externalId, municipioIbge, emenda);
        return ResponseEntity.ok(emenda);
    }

    @PostMapping("/municipio/{municipioIbge}/contrato")
    public ResponseEntity<String> ingestContratoMunicipal(
            @PathVariable String municipioIbge,
            @RequestParam String empresaCnpj,
            @RequestParam String empresaName) {
        dataIngestionService.ingestContratoMunicipal(municipioIbge, empresaCnpj, empresaName);
        return ResponseEntity.ok("Contrato registered successfully");
    }

    @PostMapping("/pessoa/societario")
    public ResponseEntity<com.tp360.core.entities.neo4j.PessoaNode> ingestPessoaSocietaria(
            @RequestBody com.tp360.core.dto.PessoaSocietariaDTO dto) {
        dataIngestionService.ingestPessoaSocietaria(dto.getPessoa(), dto.getAssociadaCnpjs());
        return ResponseEntity.ok(dto.getPessoa());
    }

    @DeleteMapping("/reset-database")
    public ResponseEntity<String> resetDatabase() {
        dataIngestionService.resetPostgresDatabase();
        return ResponseEntity.ok("PostgreSQL Database reset successfully.");
    }

    @DeleteMapping("/prune-empty")
    public ResponseEntity<String> pruneEmptyPoliticians() {
        int removed = dataIngestionService.pruneEmptyPoliticians();
        return ResponseEntity.ok("Pruned " + removed + " empty ghost politicians.");
    }
}
