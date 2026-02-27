package com.tp360.core.domain;

import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.List;

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

    @OneToMany(mappedBy = "politician", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Promise> promises = new ArrayList<>();

    @OneToMany(mappedBy = "politician", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Vote> votes = new ArrayList<>();

    // Accessors
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getExternalId() { return externalId; }
    public void setExternalId(String externalId) { this.externalId = externalId; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getParty() { return party; }
    public void setParty(String party) { this.party = party; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
    public String getPosition() { return position; }
    public void setPosition(String position) { this.position = position; }
    public List<Promise> getPromises() { return promises; }
    public void setPromises(List<Promise> promises) { this.promises = promises; }
    public List<Vote> getVotes() { return votes; }
    public void setVotes(List<Vote> votes) { this.votes = votes; }
}
