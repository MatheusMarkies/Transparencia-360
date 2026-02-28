package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;

import lombok.Data;

@Data
@Node("SessaoPlenario")
public class SessaoPlenarioNode {

    @Id
    private String id; // usually external ID composed of hash or data + local

    @Property("data")
    private String data; // YYYY-MM-DD format

    @Property("tipo")
    private String tipo; // "Sessão Deliberativa"

    @Property("local")
    private String local; // "DF"
}
