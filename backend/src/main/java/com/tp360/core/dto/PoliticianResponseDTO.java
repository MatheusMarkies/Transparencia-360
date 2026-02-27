package com.tp360.core.dto;

import com.tp360.core.domain.Politician;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.List;
import java.util.stream.Collectors;

@Data
@NoArgsConstructor
public class PoliticianResponseDTO {
    private Long id;
    private String name;
    private String party;
    private String state;
    private String position;
    // We will expand this with promises and votes later if detailed=true

    public PoliticianResponseDTO(Politician politician) {
        this.id = politician.getId();
        this.name = politician.getName();
        this.party = politician.getParty();
        this.state = politician.getState();
        this.position = politician.getPosition();
    }
    
    public static List<PoliticianResponseDTO> from(List<Politician> politicians) {
        return politicians.stream().map(PoliticianResponseDTO::new).collect(Collectors.toList());
    }
}
