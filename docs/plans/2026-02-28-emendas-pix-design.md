# Emendas Pix (Transferências Especiais) Anomaly Detector Design

## Background
"Emendas Pix", officially known as "Transferências Especiais," allow lawmakers to send federal funds directly to municipalities without prior project approval or tied objectives. This creates a high risk of corruption, as allied mayors can launch expedited public bids ("Dispensa de Licitação") targeting companies secretly owned by or associated with campaign donors of the politician who sent the funds.

The goal is to map this circular money flow and flag it as a critical anomaly using a Neo4j Graph Database.

## User Approved Approach: "Expansão Societária de 2º Grau" (Aggressive)
Instead of matching the exact CNPJ of the campaign donor, the Rules Engine will use a 2nd-degree depth search to find associations between the **partners (sócios)** of the company that received the municipal bid and the partners/donors of the politician's campaign.

## Graph Architecture

### Nodes
- **`Politico`**: The politician sending the funds.
- **`Municipio`**: The city receiving the Transferência Especial.
- **`Empresa`**: A company (CNPJ) that is either a donor or a contractor.
- **`Pessoa`**: An individual (CPF) who is either a donor, a candidate, or a partner (sócio) of an `Empresa`.
- **`Emenda`**: Information regarding the transferred funds (Transferência Especial).

### Relationships
- `(Politico)-[:ENVIOU_EMENDA {ano, valor}]->(Municipio)`
- `(Municipio)-[:CONTRATOU {licitacao_id, valor}]->(Empresa)`
- `(Pessoa)-[:SOCIO_DE]->(Empresa)`
- `(Pessoa)-[:DOOU_PARA_CAMPANHA {ano, valor}]->(Politico)`
- `(Empresa)-[:DOOU_PARA_CAMPANHA {ano, valor}]->(Politico)` *(For historical data prior to 2016 when corporate donations were legal, or disguised donations).*

### Cypher Target Pattern (The Circular Flow)
The anomaly detector worker will run a continuous query seeking this closed circuit:

```cypher
MATCH 
  // 1. Politician sends funds to Municipality
  (p:Politico)-[emenda:ENVIOU_EMENDA]->(m:Municipio),
  
  // 2. Municipality hires a Company
  (m)-[contrato:CONTRATOU]->(e_contratada:Empresa),
  
  // 3. 2nd-Degree Societal Expansion: The hired company shares a partner/owner 
  // with a person or company that donated to the politician's campaign
  (socio:Pessoa)-[:SOCIO_DE]->(e_contratada),
  (socio)-[:DOOU_PARA_CAMPANHA]->(p) 
  
  // OR the partner owns another company that donated
  // OR the partner is family with the donor, etc. (Can be expanded)
  
RETURN p.name, m.name, e_contratada.cnpj, socio.name, emenda.valor, contrato.valor
```

## Changes Required

1. **Backend (Java Spring Boot):**
    *   Update `PoliticoNode` and `EmpresaNode`.
    *   Create new nodes: `MunicipioNode`, `PessoaNode`, `EmendaNode`.
    *   Add relationships inside `PoliticoNode` (`ENVIOU_EMENDA`) and `MunicipioNode` (`CONTRATOU`).
    *   Add `/politician/emenda`, `/municipio/contrato`, `/pessoa/doacao` ingestion endpoints in `WorkerIntegrationController` and `DataIngestionService`.
    *   Update `Politician` domain object to include `emendasPixAnomalyCount` and `emendasPixAnomalyDetails`.

2. **Data Extraction (Python Workers):**
    *   **`emendas_gatherer.py` (NEW):** Consume the Transferegov APIs (or Portal da Transparência) to extract *Transferências Especiais* mapped to politicians and target municipalities. Send `ENVIOU_EMENDA` edges to the backend.
    *   **Update `tse_batch_loader.py`:** Ensure it correctly populates `PessoaNode` and `[:DOOU_PARA_CAMPANHA]` edges.
    *   **Update `querido_diario_gatherer.py` / `transparencia_gatherer.py`:** Extract municipal contracts/bids linked to the municipalities receiving Emendas Pix and build `[:CONTRATOU]` edges.
    *   **`emendas_pix_worker.py` (NEW):** The actual Rules Engine that queries Neo4j for the circular path and flags the politician with the composite anomaly details.

3. **Master Orchestrator Integration:**
    *   Add `emendas_gatherer` and `emendas_pix_worker` to `run_all_extractions.py`.
