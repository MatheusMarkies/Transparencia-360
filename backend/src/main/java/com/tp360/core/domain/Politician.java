package com.tp360.core.domain;

import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.Transient;
import lombok.Data;

@Entity
@Table(name = "politicians")
@Data
public class Politician {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false)
    private String externalId; // ID from gov APIs (Câmara/Senado/TSE)

    @Column(nullable = false)
    private String name;

    private String party;
    private String state;
    private String position; // Deputado, Senador, etc.

    // New Performance Metrics
    private Integer absences;
    private Integer presences;
    private Double expenses;

    // A value between 0.0 and 1.0 representing how much the politician's actions
    // focus on their home state
    private Double stateAffinity;

    // Portal da Transparência / Legislative Productivity Metrics
    private Integer propositions; // Authored propositions count
    private Integer frentes; // Frentes parlamentares (caucuses) joined

    // TSE Electoral Data
    private Double declaredAssets; // Total declared assets (bens declarados ao TSE) - 2022
    private Double declaredAssets2018;
    private Double declaredAssets2014;

    // Wealth anomaly score: how many times growth exceeds max salary savings
    // >1.0 = grew more than salary allows, >5.0 = critical red flag
    private Double wealthAnomaly;

    // Staff anomaly detection results
    private Integer staffAnomalyCount; // Number of flagged suppliers/staff
    @Column(columnDefinition = "TEXT")
    private String staffAnomalyDetails; // JSON array of anomaly details

    // Rachadinha Risk Score
    private Integer cabinetRiskScore; // 0-100 indicating likelihood of rachadinha (Heuristics 1-5)
    @Column(columnDefinition = "TEXT")
    private String cabinetRiskDetails; // JSON breakdown of points per heuristic

    // Ghost Employee Detection Results
    private Integer ghostEmployeeCount;
    @Column(columnDefinition = "TEXT")
    private String ghostEmployeeDetails;

    // NLP Gazette (Querido Diário) Real Data
    private Integer nlpGazetteCount; // Number of dispensas/mentions
    private Integer nlpGazetteScore; // Aggregated score
    @Column(columnDefinition = "TEXT")
    private String nlpGazetteDetails; // JSON with array of findings (empresa, valor, modalidade, city)

    // Judicial Risk Data (DataJud)
    private Integer judicialRiskScore;
    @Column(columnDefinition = "TEXT")
    private String judicialRiskDetails;

    private Integer cabinetSize;
    @Column(columnDefinition = "TEXT")
    private String cabinetDetails;

    @OneToMany(mappedBy = "politician", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Promise> promises = new ArrayList<>();

    @OneToMany(mappedBy = "politician", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Vote> votes = new ArrayList<>();

    @Column(name = "rosie_benford_count")
    private Integer rosieBenfordCount;

    @Column(name = "rosie_duplicate_count")
    private Integer rosieDuplicateCount;

    @Column(name = "rosie_weekend_count")
    private Integer rosieWeekendCount;

    @Transient
    @JsonProperty("overallRiskScore")
    public Double getOverallRiskScore() {
        Double rachadinha = this.cabinetRiskScore != null ? this.cabinetRiskScore : 0.0;
        int abs = this.absences != null ? this.absences : 0;
        int pres = this.presences != null ? this.presences : 0;
        int totalSessions = abs + pres;

        Double absenceRisk = 0.0;
        if (totalSessions > 0) {
            // Calcula a porcentagem de faltas (0 a 100)
            absenceRisk = ((double) abs / totalSessions) * 100.0;
        }

        // Pesos: 75% Risco de Gabinete (Corrupção), 25% Faltas (Desleixo)
        Double finalScore = (rachadinha * 0.75) + (absenceRisk * 0.25);

        // Arredonda para 1 casa decimal (ex: 85.4)
        return Math.round(finalScore * 10.0) / 10.0;
    }
}
