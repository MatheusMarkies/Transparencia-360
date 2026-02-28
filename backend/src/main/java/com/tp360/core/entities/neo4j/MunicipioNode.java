package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;
import org.springframework.data.neo4j.core.schema.Relationship;

import lombok.Data;
import java.util.List;
import java.util.ArrayList;

@Data
@Node("Municipio")
public class MunicipioNode {

    @Id
    private String codigoIbge;

    @Property("name")
    private String name;

    @Property("uf")
    private String uf;

    @Relationship(type = "CONTRATOU", direction = Relationship.Direction.OUTGOING)
    private List<EmpresaNode> empresasContratadas = new ArrayList<>();
}
