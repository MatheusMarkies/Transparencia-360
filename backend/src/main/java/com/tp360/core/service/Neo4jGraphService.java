package com.tp360.core.service;

import com.tp360.core.repositories.neo4j.PoliticoNodeRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class Neo4jGraphService {

    @Autowired
    private PoliticoNodeRepository repository;

    /**
     * Finds deep cyclic triangulation networks (Laranjas -> Empresa -> Campaign)
     */
    public List<Map<String, Object>> findTriangulationPath(String politicoId) {
        return repository.findTriangulationPath(politicoId);
    }

    /**
     * Gets all connections up to 4 degrees of separation to render the neural map
     */
    public List<Map<String, Object>> getFullConnectionGraph(String politicoId) {
        return repository.getFullConnectionGraph(politicoId);
    }
}
