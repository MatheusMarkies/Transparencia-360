package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;
import org.springframework.data.neo4j.core.schema.Relationship;

import lombok.Data;
import java.util.List;
import java.util.ArrayList;

import com.tp360.core.entities.neo4j.PoliticoNode;

@Data
@Node("Pessoa")
public class PessoaNode {

    @Id
    private String cpf;

    @Property("name")
    private String name;

    @Property("is_operator")
    private Boolean isOperator;

    @Property("wealthy")
    private Boolean wealthy;

    @Relationship(type = "SOCIO_ADMINISTRADOR_DE", direction = Relationship.Direction.OUTGOING)
    private List<EmpresaNode> empresasAdministradas = new ArrayList<>();

    @Relationship(type = "SOCIO_DE", direction = Relationship.Direction.OUTGOING)
    private List<EmpresaNode> participacoes = new ArrayList<>();

    @Relationship(type = "APORTOU_CAPITAL_EM", direction = Relationship.Direction.OUTGOING)
    private List<EmpresaNode> aportes = new ArrayList<>();

    @Relationship(type = "DOOU_PARA_CAMPANHA", direction = Relationship.Direction.OUTGOING)
    private List<PoliticoNode> doacoes = new ArrayList<>();
}
