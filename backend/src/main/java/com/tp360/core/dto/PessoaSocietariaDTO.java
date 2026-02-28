package com.tp360.core.dto;

import lombok.Data;
import java.util.List;
import com.tp360.core.entities.neo4j.PessoaNode;

@Data
public class PessoaSocietariaDTO {
    private PessoaNode pessoa;
    private List<String> associadaCnpjs;
}
