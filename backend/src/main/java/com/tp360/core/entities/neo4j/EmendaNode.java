package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;
import org.springframework.data.neo4j.core.schema.Relationship;

import lombok.Data;

@Data
@Node("Emenda")
public class EmendaNode {

    @Id
    private String id; // format: ano_numero

    @Property("ano")
    private Integer ano;

    @Property("valor")
    private Double valor;

    @Property("tipo")
    private String tipo; // e.g., "Transferência Especial"
}
