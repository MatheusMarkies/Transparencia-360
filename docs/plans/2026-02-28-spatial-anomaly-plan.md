# Spatial Anomaly Detector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a teleportation detection system that cross-references plenary presences in Brasília with expense receipts generated in other states on the same day using Neo4j.

**Architecture:** We will update the backend Neo4j nodes (`PoliticoNode`) and `DataIngestionService` to accept new relationships `ESTEVE_PRESENTE_EM` (`SessaoPlenario`) and `GEROU_DESPESA` (`Despesa`). Then, update the Python extractors (`absences_worker.py` and `expenses_worker.py`) to send this detailed data. Finally, a new `spatial_anomaly_worker.py` will query Neo4j to find intersections where a politician was present in a session in DF but generated an expense requiring physical presence (like meals or lodging) in another state on the same exact day.

**Tech Stack:** Python 3 (Workers), Java 17 + Spring Boot + Spring Data Neo4j (Backend), Neo4j (Graph Database).

---

### Task 1: Backend Domain and Neo4j Entity Updates

**Files:**
- Modify: `backend/src/main/java/com/tp360/core/domain/Politician.java`
- Modify: `backend/src/main/java/com/tp360/core/entities/neo4j/PoliticoNode.java`
- Create: `backend/src/main/java/com/tp360/core/entities/neo4j/SessaoPlenarioNode.java`
- Create: `backend/src/main/java/com/tp360/core/entities/neo4j/DespesaNode.java`

**Step 1:** Create `SessaoPlenarioNode` and `DespesaNode` in the Neo4j entities package.
**Step 2:** Update `PoliticoNode` to include the respective `@Relationship` lists.
**Step 3:** Update `Politician` domain model to include `Integer teleportAnomalyCount` and `String teleportAnomalyDetails`.
**Step 4:** Ensure the project compiles successfully (`./gradlew build -x test`).

---

### Task 2: Backend REST API and Ingestion Service Updates

**Files:**
- Modify: `backend/src/main/java/com/tp360/core/service/DataIngestionService.java`
- Modify: `backend/src/main/java/com/tp360/core/controller/WorkerIntegrationController.java`

**Step 1:** Update `DataIngestionService.ingestPolitician` and `mergeFields` to handle the new `teleportAnomalyCount` and `teleportAnomalyDetails` fields.
**Step 2:** Add methods in `DataIngestionService` for `ingestSessaoPlenario(String externalId, SessaoPlenarioNode sessao)` and `ingestDespesa(String externalId, DespesaNode despesa)`. Note: these should link to the politician node. You may also need to update repositories.
**Step 3:** Add corresponding endpoints in `WorkerIntegrationController` mapping to POST `/api/v1/ingest/politician/{externalId}/sessao` and `/api/v1/ingest/politician/{externalId}/despesa`.
**Step 4:** Verify compilation (`./gradlew build -x test`).

---

### Task 3: Python Workers - Extracting Granular Data

**Files:**
- Modify: `workers/src/gatherers/absences_worker.py`
- Modify: `workers/src/gatherers/expenses_worker.py`

**Step 1:** In `absences_worker.py`, modify `_count_plenary_events` to not only count but also POST each "Sessão Deliberativa" (date, type) to the new backend endpoint for the given politician.
**Step 2:** In `expenses_worker.py`, modify `_aggregate_expenses` to POST individual receipts (date, uf, valor, category, supplier) to the new backend endpoint IF the category indicates mandatory physical presence (e.g., "FORNECIMENTO DE ALIMENTAÇÃO", "HOSPEDAGEM", "LOCAÇÃO OU FRETAMENTO DE VEÍCULOS AUTOMOTORES").
**Step 3:** Run both workers against a single deputy to verify data is inserted into Neo4j without errors.

---

### Task 4: Spatial Anomaly Worker (The Rules Engine)

**Files:**
- Create: `workers/src/gatherers/spatial_anomaly_worker.py`

**Step 1:** Write `spatial_anomaly_worker.py` that connects to the Neo4j database using the official python driver (`neo4j`).
**Step 2:** Execute the Cypher query:
```cypher
MATCH (p:Politico)-[:ESTEVE_PRESENTE_EM]->(s:SessaoPlenario),
      (p)-[:GEROU_DESPESA]->(d:Despesa)
WHERE s.data = d.dataEmissao
      AND d.ufFornecedor <> 'DF'
      AND d.ufFornecedor <> 'NA'
RETURN p.externalId as id, p.name as name, s.data as dataSessao, d.categoria as categoria, d.nomeFornecedor as fornecedor, d.valorDocumento as valor, d.ufFornecedor as uf
```
**Step 3:** Aggregate the anomalies per politician, construct a JSON payload with the list of conflicting receipts, and calculate the total count.
**Step 4:** Send a POST to the standard `/api/v1/ingest/politician` endpoint with the `teleportAnomalyCount` and `teleportAnomalyDetails` fields populated for each anomalous politician.
**Step 5:** Run the worker and verify it successfully updates the backend.
