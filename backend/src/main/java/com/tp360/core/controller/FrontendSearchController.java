package com.tp360.core.controller;

import com.tp360.core.domain.Politician;
import com.tp360.core.dto.PoliticianResponseDTO;
import com.tp360.core.repository.PoliticianRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/politicians")
@CrossOrigin(origins = "*") // Allow frontend access
public class FrontendSearchController {

    private final PoliticianRepository politicianRepository;

    public FrontendSearchController(PoliticianRepository politicianRepository) {
        this.politicianRepository = politicianRepository;
    }

    @GetMapping("/search")
    public ResponseEntity<List<PoliticianResponseDTO>> searchPoliticians(
            @RequestParam(name = "name") String nameQuery) {
        
        List<Politician> results = politicianRepository.findByNameContainingIgnoreCase(nameQuery);
        return ResponseEntity.ok(PoliticianResponseDTO.from(results));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Politician> getPoliticianDetails(@PathVariable Long id) {
        Optional<Politician> politician = politicianRepository.findById(id);
        
        return politician.map(ResponseEntity::ok)
                         .orElse(ResponseEntity.notFound().build());
    }
}
