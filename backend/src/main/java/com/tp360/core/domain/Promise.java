package com.tp360.core.domain;

import jakarta.persistence.*;
import java.time.LocalDate;

@Entity
@Table(name = "promises")
public class Promise {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "politician_id", nullable = false)
    @com.fasterxml.jackson.annotation.JsonIgnore
    private Politician politician;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String text;

    private String source; // URL or Document where it was extracted
    private LocalDate extractionDate;

    // Accessors
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Politician getPolitician() {
        return politician;
    }

    public void setPolitician(Politician politician) {
        this.politician = politician;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public LocalDate getExtractionDate() {
        return extractionDate;
    }

    public void setExtractionDate(LocalDate extractionDate) {
        this.extractionDate = extractionDate;
    }
}
