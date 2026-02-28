package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;
import org.springframework.data.neo4j.core.schema.Relationship;

import lombok.Data;
import java.util.List;
import java.util.ArrayList;

@Data
@Node("Politico")
public class PoliticoNode {

    @Id
    private String id;

    @Property("name")
    private String name;

    @Property("party")
    private String party;

    @Property("state")
    private String state;

    @Relationship(type = "CONTRATOU", direction = Relationship.Direction.OUTGOING)
    private List<EmpresaNode> empresasContratadas = new ArrayList<>();

    @Relationship(type = "ESTEVE_PRESENTE_EM", direction = Relationship.Direction.OUTGOING)
    private List<SessaoPlenarioNode> sessoesPlenario = new ArrayList<>();

    @Relationship(type = "GEROU_DESPESA", direction = Relationship.Direction.OUTGOING)
    private List<DespesaNode> despesas = new ArrayList<>();

    @Relationship(type = "ENVIOU_EMENDA", direction = Relationship.Direction.OUTGOING)
    private List<MunicipioNode> municipiosBeneficiados = new ArrayList<>();
}
