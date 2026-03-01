# Rachadinha Scoring System Design

## Overview
A powerful heuristic + ML scoring engine designed to detect "Rachadinha" (kickback schemes) and staff irregularities in deputies' cabinets. Instead of requiring a dedicated Graph Database (like Neo4j), we leverage PostgreSQL with Recursive CTEs to achieve deep relational matching without increasing infrastructure complexity.

## The 3 Core Heuristics

### 1. The Compulsory Donor ("Doador Compulsório")
- **Logic:** Identifies staff members whose campaign donations to the politician are suspiciously high compared to their disclosed official salaries. 
- **Implementation:** The worker pulls salary data from the Câmara API (Servidores do Gabinete) and cross-references it with TSE campaign donation data.
- **Scoring:** The ratio `(Total Donated / Annual Salary)` directly influences the score.
- **Weight:** High (50 points).

### 2. The Revolving Door ("Porta Giratória")
- **Logic:** Evaluates the turnover rate of the cabinet. High turnover often indicates the use of "laranjas" (straw men) or schemes to capture severance pay.
- **Implementation:** The worker historically tracks appointments (nomeações) and dismissals (exonerações) using the Câmara API / Diário Oficial. 
- **Scoring:** Cabinets with turnover rates `> 3x` the House average are heavily penalized.
- **Weight:** Medium (20 points).

### 3. Triangulation of Funds ("Triangulação de Verbas")
- **Logic:** Detects complex schemes where a politician spends their `Cota Parlamentar` (CEAP) on a company owned by one of their own staff members (acting as a partner/sócio).
- **Implementation:** Uses PostgreSQL Recursive CTEs and advanced Joins to find the pattern: `Politician -> Pays CEAP -> Company X <- Owned By <- Staff Member`. This requires joining expense data with Receita Federal / CNPJ partner data.
- **Scoring:** Critical red flag if the cycle closes.
- **Weight:** Critical (80 points).

## Architecture

### 1. Data Ingestion (Python Workers)
- `rachadinha_worker.py`: Gathers data from Gov APIs (Câmara, TSE, Receita) daily/weekly. 
- It aggregates these three complex datasets and posts the raw evidence to the Spring Boot backend.

### 2. The Rules & Scoring Engine (Spring Boot)
- **Service:** `RiskScoringService.java`.
- Receives the raw heuristic data, applies the mathematical weights, and normalizes a final `Total Risk Score` (0-100).
- Persists the results to a new database entity (`cabinet_risk_score` or an extension of `Politician`).

### 3. Storage (PostgreSQL)
- `staff_member`: Stores employees (CPF, Name, Salary, Start/End Dates).
- `cabinet_risk_score`: Stores `politician_id`, `total_score`, and a JSON `heuristics_breakdown` containing exact points and flags.

### 4. Frontend
- Displays a visual "Radar de Probabilidade" or Gauge Chart on the Politician Dashboard for immediate public awareness.
