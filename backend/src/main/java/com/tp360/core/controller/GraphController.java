package com.tp360.core.controller;

import com.tp360.core.service.Neo4jGraphService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/graph")
@CrossOrigin(origins = { "http://localhost:5173", "http://localhost:3000" }) // Vite + Generic
public class GraphController {

    @Autowired
    private Neo4jGraphService graphService;

    @GetMapping("/triangulation/{politicoId}")
    public ResponseEntity<List<Map<String, Object>>> getTriangulation(@PathVariable String politicoId) {
        return ResponseEntity.ok(graphService.findTriangulationPath(politicoId));
    }

    @GetMapping("/network/{politicoId}")
    public ResponseEntity<List<Map<String, Object>>> getNetworkMap(@PathVariable String politicoId) {
        return ResponseEntity.ok(graphService.getFullConnectionGraph(politicoId));
    }
}
