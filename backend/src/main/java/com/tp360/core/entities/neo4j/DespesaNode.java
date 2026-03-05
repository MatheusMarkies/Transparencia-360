package com.tp360.core.entities.neo4j;

import org.springframework.data.neo4j.core.schema.Id;
import org.springframework.data.neo4j.core.schema.Node;
import org.springframework.data.neo4j.core.schema.Property;

import lombok.Data;

@Data
@Node("Despesa")
public class DespesaNode {

    @Id
    private String id; // usually external ID composed of object details

    @Property("dataEmissao")
    private String dataEmissao; // YYYY-MM-DD format

    @Property("ufFornecedor")
    private String ufFornecedor;

    @Property("categoria")
    private String categoria;

    @Property("valorDocumento")
    private Double valorDocumento;

    @Property("nomeFornecedor")
    private String nomeFornecedor;

    @Property("rosieAnomalies")
    private String rosieAnomalies; // JSON string with all anomalies detected by Rosie
}
