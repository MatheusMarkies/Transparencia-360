package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;
import org.springframework.data.neo4j.core.schema.Relationship;

import lombok.Data;
import java.util.List;
import java.util.ArrayList;

@Data
@Node("Empresa")
public class EmpresaNode {

    @Id
    private String cnpj;

    @Property("name")
    private String name;

    @Property("risk_level")
    private String riskLevel;
}
