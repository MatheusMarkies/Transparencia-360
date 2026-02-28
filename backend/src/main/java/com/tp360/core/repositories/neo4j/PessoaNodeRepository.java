package com.tp360.core.repositories.neo4j;

import com.tp360.core.entities.neo4j.PessoaNode;
import org.springframework.data.neo4j.repository.Neo4jRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface PessoaNodeRepository extends Neo4jRepository<PessoaNode, String> {
}
