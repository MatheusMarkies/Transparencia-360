package com.tp360.core.domain;

import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.Transient;

@Entity
@Table(name = "politicians")
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

    // Accessors
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getExternalId() {
        return externalId;
    }

    public void setExternalId(String externalId) {
        this.externalId = externalId;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getParty() {
        return party;
    }

    public void setParty(String party) {
        this.party = party;
    }

    public String getState() {
        return state;
    }

    public void setState(String state) {
        this.state = state;
    }

    public String getPosition() {
        return position;
    }

    public void setPosition(String position) {
        this.position = position;
    }

    public Integer getAbsences() {
        return absences;
    }

    public void setAbsences(Integer absences) {
        this.absences = absences;
    }

    public Double getExpenses() {
        return expenses;
    }

    public void setExpenses(Double expenses) {
        this.expenses = expenses;
    }

    public Double getStateAffinity() {
        return stateAffinity;
    }

    public void setStateAffinity(Double stateAffinity) {
        this.stateAffinity = stateAffinity;
    }

    public Integer getPropositions() {
        return propositions;
    }

    public void setPropositions(Integer propositions) {
        this.propositions = propositions;
    }

    public Integer getFrentes() {
        return frentes;
    }

    public void setFrentes(Integer frentes) {
        this.frentes = frentes;
    }

    public Double getDeclaredAssets() {
        return declaredAssets;
    }

    public void setDeclaredAssets(Double declaredAssets) {
        this.declaredAssets = declaredAssets;
    }

    public Double getDeclaredAssets2018() {
        return declaredAssets2018;
    }

    public void setDeclaredAssets2018(Double declaredAssets2018) {
        this.declaredAssets2018 = declaredAssets2018;
    }

    public Double getDeclaredAssets2014() {
        return declaredAssets2014;
    }

    public void setDeclaredAssets2014(Double declaredAssets2014) {
        this.declaredAssets2014 = declaredAssets2014;
    }

    public Double getWealthAnomaly() {
        return wealthAnomaly;
    }

    public void setWealthAnomaly(Double wealthAnomaly) {
        this.wealthAnomaly = wealthAnomaly;
    }

    public Integer getStaffAnomalyCount() {
        return staffAnomalyCount;
    }

    public void setStaffAnomalyCount(Integer staffAnomalyCount) {
        this.staffAnomalyCount = staffAnomalyCount;
    }

    public String getStaffAnomalyDetails() {
        return staffAnomalyDetails;
    }

    public void setStaffAnomalyDetails(String staffAnomalyDetails) {
        this.staffAnomalyDetails = staffAnomalyDetails;
    }

    public List<Promise> getPromises() {
        return promises;
    }

    public void setPromises(List<Promise> promises) {
        this.promises = promises;
    }

    public List<Vote> getVotes() {
        return votes;
    }

    public void setVotes(List<Vote> votes) {
        this.votes = votes;
    }

    public Integer getCabinetRiskScore() {
        return cabinetRiskScore;
    }

    public void setCabinetRiskScore(Integer cabinetRiskScore) {
        this.cabinetRiskScore = cabinetRiskScore;
    }

    public String getCabinetRiskDetails() {
        return cabinetRiskDetails;
    }

    public void setCabinetRiskDetails(String cabinetRiskDetails) {
        this.cabinetRiskDetails = cabinetRiskDetails;
    }

    public Integer getGhostEmployeeCount() {
        return ghostEmployeeCount;
    }

    public void setGhostEmployeeCount(Integer ghostEmployeeCount) {
        this.ghostEmployeeCount = ghostEmployeeCount;
    }

    public String getGhostEmployeeDetails() {
        return ghostEmployeeDetails;
    }

    public void setGhostEmployeeDetails(String ghostEmployeeDetails) {
        this.ghostEmployeeDetails = ghostEmployeeDetails;
    }

    public Integer getNlpGazetteCount() {
        return nlpGazetteCount;
    }

    public void setNlpGazetteCount(Integer nlpGazetteCount) {
        this.nlpGazetteCount = nlpGazetteCount;
    }

    public Integer getNlpGazetteScore() {
        return nlpGazetteScore;
    }

    public void setNlpGazetteScore(Integer nlpGazetteScore) {
        this.nlpGazetteScore = nlpGazetteScore;
    }

    public String getNlpGazetteDetails() {
        return nlpGazetteDetails;
    }

    public void setNlpGazetteDetails(String nlpGazetteDetails) {
        this.nlpGazetteDetails = nlpGazetteDetails;
    }

    // Teleportation Anomaly (Spatial Match)
    private Integer teleportAnomalyCount;
    @Column(columnDefinition = "TEXT")
    private String teleportAnomalyDetails;

    public Integer getTeleportAnomalyCount() {
        return teleportAnomalyCount;
    }

    public void setTeleportAnomalyCount(Integer teleportAnomalyCount) {
        this.teleportAnomalyCount = teleportAnomalyCount;
    }

    public String getTeleportAnomalyDetails() {
        return teleportAnomalyDetails;
    }

    public void setTeleportAnomalyDetails(String teleportAnomalyDetails) {
        this.teleportAnomalyDetails = teleportAnomalyDetails;
    }

    // Emendas Pix Anomaly (Circular Flow)
    private Integer emendasPixAnomalyCount;
    @Column(columnDefinition = "TEXT")
    private String emendasPixAnomalyDetails;

    public Integer getEmendasPixAnomalyCount() {
        return emendasPixAnomalyCount;
    }

    public void setEmendasPixAnomalyCount(Integer emendasPixAnomalyCount) {
        this.emendasPixAnomalyCount = emendasPixAnomalyCount;
    }

    public String getEmendasPixAnomalyDetails() {
        return emendasPixAnomalyDetails;
    }

    public void setEmendasPixAnomalyDetails(String emendasPixAnomalyDetails) {
        this.emendasPixAnomalyDetails = emendasPixAnomalyDetails;
    }

    public Integer getJudicialRiskScore() {
        return judicialRiskScore;
    }

    public void setJudicialRiskScore(Integer judicialRiskScore) {
        this.judicialRiskScore = judicialRiskScore;
    }

    public String getJudicialRiskDetails() {
        return judicialRiskDetails;
    }

    public void setJudicialRiskDetails(String judicialRiskDetails) {
        this.judicialRiskDetails = judicialRiskDetails;
    }

    public Integer getCabinetSize() {
        return cabinetSize;
    }

    public void setCabinetSize(Integer cabinetSize) {
        this.cabinetSize = cabinetSize;
    }

    public String getCabinetDetails() {
        return cabinetDetails;
    }

    public void setCabinetDetails(String cabinetDetails) {
        this.cabinetDetails = cabinetDetails;
    }

    public Integer getPresences() {
        return presences;
    }

    public void setPresences(Integer presences) {
        this.presences = presences;
    }
}
