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
}
