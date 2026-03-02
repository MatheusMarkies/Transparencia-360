package com.tp360.core.service;

import com.tp360.core.domain.Politician;
import com.tp360.core.domain.Promise;
import com.tp360.core.domain.Vote;
import com.tp360.core.repository.PoliticianRepository;
import com.tp360.core.repository.PromiseRepository;
import com.tp360.core.repository.VoteRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class DataIngestionService {

    private final PoliticianRepository politicianRepository;
    private final PromiseRepository promiseRepository;
    private final VoteRepository voteRepository;

    private final com.tp360.core.repositories.neo4j.PoliticoNodeRepository politicoNodeRepository;
    private final com.tp360.core.repositories.neo4j.SessaoPlenarioNodeRepository sessaoPlenarioNodeRepository;
    private final com.tp360.core.repositories.neo4j.DespesaNodeRepository despesaNodeRepository;

    private final com.tp360.core.repositories.neo4j.MunicipioNodeRepository municipioNodeRepository;
    private final com.tp360.core.repositories.neo4j.PessoaNodeRepository pessoaNodeRepository;
    private final com.tp360.core.repositories.neo4j.EmendaNodeRepository emendaNodeRepository;
    private final com.tp360.core.repositories.neo4j.EmpresaNodeRepository empresaNodeRepository;

    @org.springframework.beans.factory.annotation.Autowired
    public DataIngestionService(PoliticianRepository politicianRepository,
            PromiseRepository promiseRepository,
            VoteRepository voteRepository,
            com.tp360.core.repositories.neo4j.PoliticoNodeRepository politicoNodeRepository,
            com.tp360.core.repositories.neo4j.SessaoPlenarioNodeRepository sessaoPlenarioNodeRepository,
            com.tp360.core.repositories.neo4j.DespesaNodeRepository despesaNodeRepository,
            com.tp360.core.repositories.neo4j.MunicipioNodeRepository municipioNodeRepository,
            com.tp360.core.repositories.neo4j.PessoaNodeRepository pessoaNodeRepository,
            com.tp360.core.repositories.neo4j.EmendaNodeRepository emendaNodeRepository,
            com.tp360.core.repositories.neo4j.EmpresaNodeRepository empresaNodeRepository) {
        this.politicianRepository = politicianRepository;
        this.promiseRepository = promiseRepository;
        this.voteRepository = voteRepository;
        this.politicoNodeRepository = politicoNodeRepository;
        this.sessaoPlenarioNodeRepository = sessaoPlenarioNodeRepository;
        this.despesaNodeRepository = despesaNodeRepository;
        this.municipioNodeRepository = municipioNodeRepository;
        this.pessoaNodeRepository = pessoaNodeRepository;
        this.emendaNodeRepository = emendaNodeRepository;
        this.empresaNodeRepository = empresaNodeRepository;
    }

    @Transactional("transactionManager")
    public Politician ingestPolitician(Politician data) {
        // 1. Try exact match by externalId (primary key for upsert)
        Optional<Politician> existing = politicianRepository.findByExternalId(data.getExternalId());

        // 2. Fallback: try name-based match to prevent duplicates from different
        // workers
        if (existing.isEmpty() && data.getName() != null) {
            existing = politicianRepository.findFirstByNameIgnoreCase(data.getName());
        }

        if (existing.isPresent()) {
            Politician p = existing.get();
            // Always update externalId to the latest one
            if (data.getExternalId() != null) {
                p.setExternalId(data.getExternalId());
            }
            if (data.getName() != null) {
                p.setName(data.getName());
            }
            if (data.getParty() != null) {
                p.setParty(data.getParty());
            }
            if (data.getState() != null) {
                p.setState(data.getState());
            }
            if (data.getPosition() != null) {
                p.setPosition(data.getPosition());
            }
            if (data.getAbsences() != null) {
                p.setAbsences(data.getAbsences());
            }
            if (data.getExpenses() != null) {
                p.setExpenses(data.getExpenses());
            }
            if (data.getStateAffinity() != null) {
                p.setStateAffinity(data.getStateAffinity());
            }
            if (data.getPropositions() != null) {
                p.setPropositions(data.getPropositions());
            }
            if (data.getFrentes() != null) {
                p.setFrentes(data.getFrentes());
            }
            if (data.getDeclaredAssets() != null) {
                p.setDeclaredAssets(data.getDeclaredAssets());
            }
            if (data.getDeclaredAssets2018() != null) {
                p.setDeclaredAssets2018(data.getDeclaredAssets2018());
            }
            if (data.getDeclaredAssets2014() != null) {
                p.setDeclaredAssets2014(data.getDeclaredAssets2014());
            }
            if (data.getWealthAnomaly() != null) {
                p.setWealthAnomaly(data.getWealthAnomaly());
            }
            if (data.getStaffAnomalyCount() != null) {
                p.setStaffAnomalyCount(data.getStaffAnomalyCount());
            }
            if (data.getStaffAnomalyDetails() != null) {
                p.setStaffAnomalyDetails(data.getStaffAnomalyDetails());
            }
            if (data.getCabinetRiskScore() != null) {
                p.setCabinetRiskScore(data.getCabinetRiskScore());
            }
            if (data.getCabinetRiskDetails() != null) {
                p.setCabinetRiskDetails(data.getCabinetRiskDetails());
            }
            if (data.getTeleportAnomalyCount() != null) {
                p.setTeleportAnomalyCount(data.getTeleportAnomalyCount());
            }
            if (data.getTeleportAnomalyDetails() != null) {
                p.setTeleportAnomalyDetails(data.getTeleportAnomalyDetails());
            }
            if (data.getNlpGazetteCount() != null) {
                p.setNlpGazetteCount(data.getNlpGazetteCount());
            }
            if (data.getNlpGazetteScore() != null) {
                p.setNlpGazetteScore(data.getNlpGazetteScore());
            }
            if (data.getNlpGazetteDetails() != null) {
                p.setNlpGazetteDetails(data.getNlpGazetteDetails());
            }
            if (data.getJudicialRiskScore() != null) {
                p.setJudicialRiskScore(data.getJudicialRiskScore());
            }
            if (data.getJudicialRiskDetails() != null) {
                p.setJudicialRiskDetails(data.getJudicialRiskDetails());
            }
            if (data.getCabinetSize() != null) {
                p.setCabinetSize(data.getCabinetSize());
            }
            if (data.getCabinetDetails() != null) {
                p.setCabinetDetails(data.getCabinetDetails());
            }
            Politician saved = politicianRepository.save(p);
            try {
                upsertNeo4jPolitico(saved);
            } catch (Exception e) {
                // Log and continue - don't fail the Postgres ingestion due to Neo4j lock
                org.slf4j.LoggerFactory.getLogger(DataIngestionService.class)
                        .warn("Non-critical Neo4j update failed for {}: {}", saved.getExternalId(), e.getMessage());
            }
            return saved;
        }
        Politician saved = politicianRepository.save(data);
        try {
            upsertNeo4jPolitico(saved);
        } catch (Exception e) {
            org.slf4j.LoggerFactory.getLogger(DataIngestionService.class)
                    .warn("Non-critical Neo4j update failed for {}: {}", saved.getExternalId(), e.getMessage());
        }
        return saved;
    }

    private void upsertNeo4jPolitico(Politician p) {
        if (p.getExternalId() == null)
            return;
        com.tp360.core.entities.neo4j.PoliticoNode node = politicoNodeRepository.findById(p.getExternalId())
                .orElseGet(() -> {
                    com.tp360.core.entities.neo4j.PoliticoNode n = new com.tp360.core.entities.neo4j.PoliticoNode();
                    n.setId(p.getExternalId());
                    return n;
                });
        node.setName(p.getName());
        node.setParty(p.getParty());
        node.setState(p.getState());
        politicoNodeRepository.save(node);
    }

    /**
     * Remove duplicate politicians keeping the entry with the most complete data.
     * Groups by name (case-insensitive) and merges fields from duplicates into the
     * survivor before deleting extras.
     */
    @Transactional("transactionManager")
    public int deduplicatePoliticians() {
        List<Politician> all = politicianRepository.findAll();
        java.util.Map<String, List<Politician>> byName = new java.util.HashMap<>();

        for (Politician p : all) {
            String key = p.getName().trim().toLowerCase();
            byName.computeIfAbsent(key, k -> new java.util.ArrayList<>()).add(p);
        }

        int removed = 0;
        for (java.util.Map.Entry<String, List<Politician>> entry : byName.entrySet()) {
            List<Politician> dupes = entry.getValue();
            if (dupes.size() <= 1)
                continue;

            // Pick the one with the most non-null fields as the survivor
            Politician survivor = dupes.stream()
                    .max(java.util.Comparator.comparingInt(this::countNonNullFields))
                    .orElse(dupes.get(0));

            // Merge fields from all duplicates into survivor
            for (Politician dupe : dupes) {
                if (dupe.getId().equals(survivor.getId()))
                    continue;
                mergeFields(survivor, dupe);
                politicianRepository.delete(dupe);
                removed++;
            }
            politicianRepository.save(survivor);
        }
        return removed;
    }

    private int countNonNullFields(Politician p) {
        int count = 0;
        if (p.getExternalId() != null)
            count++;
        if (p.getParty() != null)
            count++;
        if (p.getState() != null)
            count++;
        if (p.getPosition() != null)
            count++;
        if (p.getAbsences() != null)
            count++;
        if (p.getExpenses() != null)
            count++;
        if (p.getStateAffinity() != null)
            count++;
        if (p.getPropositions() != null)
            count++;
        if (p.getDeclaredAssets() != null)
            count++;
        if (p.getCabinetRiskScore() != null)
            count++;
        if (p.getStaffAnomalyCount() != null)
            count++;
        if (p.getTeleportAnomalyCount() != null)
            count++;
        if (p.getNlpGazetteCount() != null)
            count++;
        if (p.getJudicialRiskScore() != null)
            count++;
        if (p.getCabinetSize() != null)
            count++;
        if (p.getCabinetDetails() != null)
            count++;
        return count;
    }

    private void mergeFields(Politician survivor, Politician source) {
        if (survivor.getParty() == null && source.getParty() != null)
            survivor.setParty(source.getParty());
        if (survivor.getState() == null && source.getState() != null)
            survivor.setState(source.getState());
        if (survivor.getPosition() == null && source.getPosition() != null)
            survivor.setPosition(source.getPosition());
        if (survivor.getAbsences() == null && source.getAbsences() != null)
            survivor.setAbsences(source.getAbsences());
        if (survivor.getExpenses() == null && source.getExpenses() != null)
            survivor.setExpenses(source.getExpenses());
        if (survivor.getStateAffinity() == null && source.getStateAffinity() != null)
            survivor.setStateAffinity(source.getStateAffinity());
        if (survivor.getPropositions() == null && source.getPropositions() != null)
            survivor.setPropositions(source.getPropositions());
        if (survivor.getFrentes() == null && source.getFrentes() != null)
            survivor.setFrentes(source.getFrentes());
        if (survivor.getDeclaredAssets() == null && source.getDeclaredAssets() != null)
            survivor.setDeclaredAssets(source.getDeclaredAssets());
        if (survivor.getDeclaredAssets2018() == null && source.getDeclaredAssets2018() != null)
            survivor.setDeclaredAssets2018(source.getDeclaredAssets2018());
        if (survivor.getDeclaredAssets2014() == null && source.getDeclaredAssets2014() != null)
            survivor.setDeclaredAssets2014(source.getDeclaredAssets2014());
        if (survivor.getWealthAnomaly() == null && source.getWealthAnomaly() != null)
            survivor.setWealthAnomaly(source.getWealthAnomaly());
        if (survivor.getStaffAnomalyCount() == null && source.getStaffAnomalyCount() != null)
            survivor.setStaffAnomalyCount(source.getStaffAnomalyCount());
        if (survivor.getStaffAnomalyDetails() == null && source.getStaffAnomalyDetails() != null)
            survivor.setStaffAnomalyDetails(source.getStaffAnomalyDetails());
        if (survivor.getCabinetRiskScore() == null && source.getCabinetRiskScore() != null)
            survivor.setCabinetRiskScore(source.getCabinetRiskScore());
        if (survivor.getCabinetRiskDetails() == null && source.getCabinetRiskDetails() != null)
            survivor.setCabinetRiskDetails(source.getCabinetRiskDetails());
        if (survivor.getTeleportAnomalyCount() == null && source.getTeleportAnomalyCount() != null)
            survivor.setTeleportAnomalyCount(source.getTeleportAnomalyCount());
        if (survivor.getTeleportAnomalyDetails() == null && source.getTeleportAnomalyDetails() != null)
            survivor.setTeleportAnomalyDetails(source.getTeleportAnomalyDetails());
        if (survivor.getNlpGazetteCount() == null && source.getNlpGazetteCount() != null)
            survivor.setNlpGazetteCount(source.getNlpGazetteCount());
        if (survivor.getNlpGazetteScore() == null && source.getNlpGazetteScore() != null)
            survivor.setNlpGazetteScore(source.getNlpGazetteScore());
        if (survivor.getNlpGazetteDetails() == null && source.getNlpGazetteDetails() != null)
            survivor.setNlpGazetteDetails(source.getNlpGazetteDetails());
        if (survivor.getJudicialRiskScore() == null && source.getJudicialRiskScore() != null)
            survivor.setJudicialRiskScore(source.getJudicialRiskScore());
        if (survivor.getJudicialRiskDetails() == null && source.getJudicialRiskDetails() != null)
            survivor.setJudicialRiskDetails(source.getJudicialRiskDetails());
        if (survivor.getCabinetSize() == null && source.getCabinetSize() != null)
            survivor.setCabinetSize(source.getCabinetSize());
        if (survivor.getCabinetDetails() == null && source.getCabinetDetails() != null)
            survivor.setCabinetDetails(source.getCabinetDetails());
    }

    @Transactional("transactionManager")
    public Promise ingestPromise(String externalPoliticianId, Promise promise) {
        Politician p = politicianRepository.findByExternalId(externalPoliticianId)
                .orElseThrow(() -> new IllegalArgumentException("Politician not found"));
        promise.setPolitician(p);
        return promiseRepository.save(promise);
    }

    @Transactional("transactionManager")
    public Vote ingestVote(String externalPoliticianId, Vote vote) {
        Politician p = politicianRepository.findByExternalId(externalPoliticianId)
                .orElseThrow(() -> new IllegalArgumentException("Politician not found"));
        vote.setPolitician(p);

        Optional<Vote> existing = voteRepository.findByPoliticianIdAndPropositionExternalId(
                p.getId(), vote.getPropositionExternalId());

        if (existing.isPresent()) {
            Vote v = existing.get();
            v.setVoteChoice(vote.getVoteChoice());
            if (vote.getPropositionSummary() != null) {
                v.setPropositionSummary(vote.getPropositionSummary());
            }
            if (vote.getCoherenceScore() != null) {
                v.setCoherenceScore(vote.getCoherenceScore());
            }
            if (vote.getCoherenceExplanation() != null) {
                v.setCoherenceExplanation(vote.getCoherenceExplanation());
            }
            return voteRepository.save(v);
        }

        return voteRepository.save(vote);
    }

    // --- Spatial Anomaly (Neo4j Graph) Ingestion ---

    @Transactional("transactionManager")
    public void ingestSessaoPlenario(String externalId, com.tp360.core.entities.neo4j.SessaoPlenarioNode sessao) {
        // Find or create politician node
        com.tp360.core.entities.neo4j.PoliticoNode politico = politicoNodeRepository.findById(externalId)
                .orElseGet(() -> {
                    com.tp360.core.entities.neo4j.PoliticoNode n = new com.tp360.core.entities.neo4j.PoliticoNode();
                    n.setId(externalId);
                    return politicoNodeRepository.save(n);
                });

        // Save session node (upsert handled by Neo4j driver + ID)
        com.tp360.core.entities.neo4j.SessaoPlenarioNode savedSessao = sessaoPlenarioNodeRepository.save(sessao);

        // Add relationship if not exists
        boolean alreadyLinked = politico.getSessoesPlenario().stream()
                .anyMatch(s -> s.getId().equals(savedSessao.getId()));

        if (!alreadyLinked) {
            politico.getSessoesPlenario().add(savedSessao);
            politicoNodeRepository.save(politico);
        }
    }

    @Transactional("transactionManager")
    public void ingestDespesa(String externalId, com.tp360.core.entities.neo4j.DespesaNode despesa) {
        // Find or create politician node
        com.tp360.core.entities.neo4j.PoliticoNode politico = politicoNodeRepository.findById(externalId)
                .orElseGet(() -> {
                    com.tp360.core.entities.neo4j.PoliticoNode n = new com.tp360.core.entities.neo4j.PoliticoNode();
                    n.setId(externalId);
                    return politicoNodeRepository.save(n);
                });

        // Save despesa node
        com.tp360.core.entities.neo4j.DespesaNode savedDespesa = despesaNodeRepository.save(despesa);

        // Add relationship
        boolean alreadyLinked = politico.getDespesas().stream()
                .anyMatch(d -> d.getId().equals(savedDespesa.getId()));

        if (!alreadyLinked) {
            politico.getDespesas().add(savedDespesa);
            politicoNodeRepository.save(politico);
        }
    }

    // --- Emendas Pix Anomaly (Circular Graph) Ingestion ---

    @Transactional("transactionManager")
    public void ingestEmendaPix(String externalPoliticianId, String municipioIbge,
            com.tp360.core.entities.neo4j.EmendaNode emenda) {
        // We need the Politician
        Optional<com.tp360.core.entities.neo4j.PoliticoNode> optPolitico = politicoNodeRepository
                .findById(externalPoliticianId);
        if (optPolitico.isEmpty())
            return;
        com.tp360.core.entities.neo4j.PoliticoNode politico = optPolitico.get();

        // Ensure Emenda is saved
        com.tp360.core.entities.neo4j.EmendaNode savedEmenda = emendaNodeRepository.save(emenda);

        // Ensure Municipio is created
        com.tp360.core.entities.neo4j.MunicipioNode municipio = municipioNodeRepository.findById(municipioIbge)
                .orElseGet(() -> {
                    com.tp360.core.entities.neo4j.MunicipioNode m = new com.tp360.core.entities.neo4j.MunicipioNode();
                    m.setCodigoIbge(municipioIbge);
                    return m;
                });

        municipioNodeRepository.save(municipio);

        // Link Politico -> Municipio (ENVIOU_EMENDA)
        boolean exists = politico.getMunicipiosBeneficiados().stream()
                .anyMatch(m -> m.getCodigoIbge().equals(municipio.getCodigoIbge()));
        if (!exists) {
            politico.getMunicipiosBeneficiados().add(municipio);
            politicoNodeRepository.save(politico);
        }
    }

    @Transactional("transactionManager")
    public void ingestContratoMunicipal(String municipioIbge, String empresaCnpj, String empresaName) {
        // Find or Create Municipio
        com.tp360.core.entities.neo4j.MunicipioNode municipio = municipioNodeRepository.findById(municipioIbge)
                .orElseGet(() -> {
                    com.tp360.core.entities.neo4j.MunicipioNode m = new com.tp360.core.entities.neo4j.MunicipioNode();
                    m.setCodigoIbge(municipioIbge);
                    return m;
                });

        // Find or Create Empresa
        com.tp360.core.entities.neo4j.EmpresaNode empresa = empresaNodeRepository.findById(empresaCnpj)
                .orElseGet(() -> {
                    com.tp360.core.entities.neo4j.EmpresaNode e = new com.tp360.core.entities.neo4j.EmpresaNode();
                    e.setCnpj(empresaCnpj);
                    e.setName(empresaName);
                    return e;
                });

        empresaNodeRepository.save(empresa);

        // Link Municipio -> Empresa (CONTRATOU)
        boolean exists = municipio.getEmpresasContratadas().stream()
                .anyMatch(e -> e.getCnpj().equals(empresa.getCnpj()));
        if (!exists) {
            municipio.getEmpresasContratadas().add(empresa);
            municipioNodeRepository.save(municipio);
        }
    }

    @Transactional("transactionManager")
    public void ingestPessoaSocietaria(com.tp360.core.entities.neo4j.PessoaNode pessoa, List<String> associadaCnpjs) {
        // Save initial Pessoa (using basic fields and Doacao list if already populated
        // by TSE gatherer)
        com.tp360.core.entities.neo4j.PessoaNode savedPessoa = pessoaNodeRepository.save(pessoa);

        // For each CNPJ, find the company and establish SOCIO_DE
        for (String cnpj : associadaCnpjs) {
            Optional<com.tp360.core.entities.neo4j.EmpresaNode> optEmpresa = empresaNodeRepository.findById(cnpj);
            if (optEmpresa.isPresent()) {
                boolean exists = savedPessoa.getParticipacoes().stream().anyMatch(e -> e.getCnpj().equals(cnpj));
                if (!exists) {
                    savedPessoa.getParticipacoes().add(optEmpresa.get());
                }
            } else {
                // Create minimal empty node so we can link
                com.tp360.core.entities.neo4j.EmpresaNode e = new com.tp360.core.entities.neo4j.EmpresaNode();
                e.setCnpj(cnpj);
                empresaNodeRepository.save(e);
                savedPessoa.getParticipacoes().add(e);
            }
        }
        pessoaNodeRepository.save(savedPessoa);
    }

    @Transactional("transactionManager")
    public void resetPostgresDatabase() {
        // Apaga na ordem correta para evitar erros de chave estrangeira (Foreign Key)
        voteRepository.deleteAll();
        promiseRepository.deleteAll();
        politicianRepository.deleteAll();
    }

}
