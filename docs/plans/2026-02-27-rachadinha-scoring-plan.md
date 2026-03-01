# Rachadinha Scoring Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a sophisticated heuristic and graph-based scoring engine to detect "Rachadinha" (kickback) patterns and irregularities in the staff and expenses of Brazilian deputies.

**Architecture:** Python workers will fetch raw data (expenses, staff, TSE donations) and compute raw heuristic signals. The Spring Boot backend will receive these signals, assign weights (H1=50, H2=20, H3=80), calculate a final risk score (0-100), and persist the `cabinet_risk_score` in PostgreSQL. The frontend will display a Radar/Gauge chart showing this risk score.

**Tech Stack:** Python (Requests, Pandas), Java 17 (Spring Boot, Spring Data JPA), PostgreSQL (Recursive CTEs), React (TailwindCSS, Recharts).

---

### Task 1: Backend Database & Entity Setup

**Files:**
- Modify: `backend/src/main/resources/application.yml` (to ensure DB connection supports complex queries if needed, though current config is fine)
- Modify: `backend/src/main/java/com/tp360/core/domain/Politician.java` (Add fields for `cabinetRiskScore` and `cabinetRiskDetails`)
- Modify: `backend/src/main/java/com/tp360/core/dto/PoliticianResponseDTO.java`

**Step 1: Update Entities and DTOs**
Add `cabinetRiskScore` (Integer, 0-100) and `cabinetRiskDetails` (String/JSON) to `Politician.java`. Update getters/setters and the constructor in `PoliticianResponseDTO.java`.

**Step 2: Update Ingestion Service**
Modify `DataIngestionService.java` to persist these new fields when `WorkerIntegrationController` receives them.

**Step 3: Rebuild Docker**
Restart the backend container to apply the DB schema changes.

---

### Task 2: Implement the Rachadinha Python Worker (Part 1 - Heuristics 1 & 2)

**Files:**
- Create: `workers/src/gatherers/rachadinha_worker.py`

**Step 1: Setup Worker Skeleton and Constants**
Create the class `RachadinhaScoringWorker` with `BackendClient` and `GovAPIClient`. 

**Step 2: Implement Heuristic 1 (Compulsory Donor)**
Fetch staff salary data (folha de pagamento) and TSE donation data. Calculate ratio `(Total Donated / Annual Salary)`.

**Step 3: Implement Heuristic 2 (Revolving Door)**
Fetch staff appointment/dismissal history. Calculate turnover rate vs house average.

---

### Task 3: Implement Heuristic 3 (Triangulation of Funds) & Scoring

**Files:**
- Modify: `workers/src/gatherers/rachadinha_worker.py`

**Step 1: Implement Heuristic 3 (Triangulation)**
Fetch expense data (CEAP) and supplier CNPJ data. Cross-reference supplier partners with staff CPFs. *Wait, actually since the Python worker processes the data in-memory before sending to the backend, we can implement the relational matching using Pandas/Dicts in Python, OR we can execute a complex CTE directly on the PostgreSQL database if the raw data is stored there. Given our architecture, the worker fetches from external APIs. So the worker will cross-reference the external Receita Federal CNPJ QSA (Quadro de Sócios) with the Staff CPFs in-memory.*

**Step 2: Apply Weighted Scoring System**
Calculate the final score out of 100 based on the 3 heuristics (H1=50, H2=20, H3=80, capped at 100).

**Step 3: Ingest Data to Backend**
Send the `cabinetRiskScore` and `cabinetRiskDetails` to the backend `/api/internal/workers/ingest/politician` endpoint.

---

### Task 4: Frontend "Radar de Probabilidade" UI

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Add new properties to Interface**
Add `cabinetRiskScore` and `cabinetRiskDetails` to the `Politician` interface.

**Step 2: Build the Radar UI Component**
Create a visual Gauge or progress bar in the Politician Dashboard showing the Risk Score (0-100) with color coding (Green 0-30, Amber 31-70, Red 71-100). Show the breakdown of points from the `cabinetRiskDetails` JSON.

---

### Task 5: Testing & Verification

**Files:**
- Run: `python workers/src/gatherers/rachadinha_worker.py`

**Step 1: Execute Worker**
Run the worker to populate the database with risk scores for the top 50 politicians.

**Step 2: Verify Frontend**
Use the browser subagent to verify the UI correctly displays the risk scoring system.
