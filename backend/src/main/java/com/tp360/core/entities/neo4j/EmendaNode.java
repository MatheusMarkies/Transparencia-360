package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;

import lombok.Data;

@Data
@Node("Emenda")
public class EmendaNode {

    @Id
    private String id;

    @Property("ano")
    private Integer ano;

    @Property("valor")
    private Double valor;

    @Property("tipo")
    private String tipo;

    @Property("funcao")
    private String funcao;

    @Property("localidade")
    private String localidade;
}