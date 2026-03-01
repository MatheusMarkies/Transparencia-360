# Spatial Anomaly (Teleportation) Detector Design

## Overview
Politicians sometimes illegally use their parliamentary quota (CEAP) to reimburse expenses made by others (e.g., campaign workers) in their home state while they are physically present in Brasília.
The "Teleportation Detector" identifies these spatial anomalies by cross-referencing plenary session attendance (in Brasília) with the location and date of expense receipts (in the politician's home state).

## Architecture Approach: Neo4j Rules Engine
We will use Neo4j's graph capabilities to detect these anomalies directly via Cypher queries, making the system elegant and scalable.

### 1. Graph Data Model Updates (Backend/Neo4j)
Currently, `AbsencesWorker` and `ExpensesWorker` only aggregate totals. We need to store individual events and receipts as nodes to enable spatial cross-matching.

#### New Nodes & Relationships
- **Node `SessaoPlenario`:**
  - Properties: `data` (YYYY-MM-DD), `tipo` (Sessão Deliberativa), `local` ('DF')
  - Relationship: `(p:Politico)-[:ESTEVE_PRESENTE_EM]->(s:SessaoPlenario)`
- **Node `Despesa`:**
  - Properties: `dataEmissao` (YYYY-MM-DD), `ufFornecedor` (State Code), `categoria` (e.g., Alimentação, Hospedagem, Locação de Veículos), `valorDocumento`, `nomeFornecedor`
  - Relationship: `(p:Politico)-[:GEROU_DESPESA]->(d:Despesa)`

### 2. Worker Updates (`workers/src/gatherers/`)
- **`absences_worker.py` (Modify or create new `plenary_attendance_worker.py`):**
  Instead of just counting absences, it will push individual `SessaoPlenario` nodes and `ESTEVE_PRESENTE_EM` relationships to Neo4j via a new backend endpoint.
- **`expenses_worker.py` (Modify or create new `detailed_expense_worker.py`):**
  Instead of just summing expenses, it will push individual `Despesa` nodes and `GEROU_DESPESA` relationships to Neo4j via a new backend endpoint. We will filter for specific categories where physical presence is mandatory (Meals, Lodging, Vehicle Rental/Fuel).

### 3. The `spatial_anomaly_worker.py` (The Detector)
This worker will act as the orchestration trigger.
1. It executes a Cypher query on Neo4j to find intersections:
   ```cypher
   MATCH (p:Politico)-[:ESTEVE_PRESENTE_EM]->(s:SessaoPlenario),
         (p)-[:GEROU_DESPESA]->(d:Despesa)
   WHERE s.data = d.dataEmissao
     AND d.ufFornecedor <> 'DF'
     AND d.ufFornecedor <> 'NA'
   RETURN p.name, p.externalId, s.data, d.categoria, d.nomeFornecedor, d.valorDocumento, d.ufFornecedor
   ```
2. It processes the results and formats them into a JSON structure (e.g., `teleportAnomalyDetails`).
3. It updates the `Politician` node with an anomaly count and the detailed JSON payload via the existing ingestion API.

### 4. Backend Updates (`backend/src/...`)
- Update `PoliticoNode.java` to include the new relationships (optional, if we only query via Cypher repository methods, we might just need the payload fields).
- Add new properties to `Politician.java` (domain) and `PoliticoEntity.java` (JPA/Neo4j entity):
  - `teleportAnomalyCount` (Integer)
  - `teleportAnomalyDetails` (String/JSON)
- Create new endpoints in `WorkerIntegrationController.java` to accept bulk ingestion of `SessaoPlenario` and `Despesa` relationships.

## Trade-offs
- **Pros:** Highly scalable, powerful querying, easy to visualize in a frontend graph, lays groundwork for future complex graph heuristic rules.
- **Cons:** Requires modifications to the backend API and database schema to handle individual node ingestion, increasing data volume in Neo4j compared to the current aggregated model.

## User Approval Needed
This design requires changes to the Java generic backend to support new node types and relationships. Is this acceptable, or should we isolate the logic entirely within a Python script that talks directly to Neo4j?
