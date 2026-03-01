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
    private String externalId;
    private String name;
    private String party;
    private String state;
    private String position;
    private Integer absences;
    private Double expenses;
    private Double stateAffinity;
    private Integer propositions;
    private Integer frentes;
    private Double declaredAssets;
    private Double declaredAssets2018;
    private Double declaredAssets2014;
    private Double wealthAnomaly;
    private Integer staffAnomalyCount;
    private String staffAnomalyDetails;
    private Integer cabinetRiskScore;
    private String cabinetRiskDetails;

    // NLP Gazette (Querido Diário) Real Data
    private Integer nlpGazetteCount;
    private Integer nlpGazetteScore;
    private String nlpGazetteDetails;

    // Judicial Risk
    private Integer judicialRiskScore;
    private String judicialRiskDetails;

    public PoliticianResponseDTO(Politician politician) {
        this.id = politician.getId();
        this.externalId = politician.getExternalId();
        this.name = politician.getName();
        this.party = politician.getParty();
        this.state = politician.getState();
        this.position = politician.getPosition();
        this.absences = politician.getAbsences();
        this.expenses = politician.getExpenses();
        this.stateAffinity = politician.getStateAffinity();
        this.propositions = politician.getPropositions();
        this.frentes = politician.getFrentes();
        this.declaredAssets = politician.getDeclaredAssets();
        this.declaredAssets2018 = politician.getDeclaredAssets2018();
        this.declaredAssets2014 = politician.getDeclaredAssets2014();
        this.wealthAnomaly = politician.getWealthAnomaly();
        this.staffAnomalyCount = politician.getStaffAnomalyCount();
        this.staffAnomalyDetails = politician.getStaffAnomalyDetails();
        this.cabinetRiskScore = politician.getCabinetRiskScore();
        this.cabinetRiskDetails = politician.getCabinetRiskDetails();
        this.nlpGazetteCount = politician.getNlpGazetteCount();
        this.nlpGazetteScore = politician.getNlpGazetteScore();
        this.nlpGazetteDetails = politician.getNlpGazetteDetails();
        this.judicialRiskScore = politician.getJudicialRiskScore();
        this.judicialRiskDetails = politician.getJudicialRiskDetails();
    }

    public static List<PoliticianResponseDTO> from(List<Politician> politicians) {
        return politicians.stream().map(PoliticianResponseDTO::new).collect(Collectors.toList());
    }
}
