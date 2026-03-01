# Massive Data Ingestion Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build transactional API clients and batch processing pipelines to ingest complete datasets (Receita Federal QSA, TSE, Portal da Transparência, DataJud, etc.) to uncover 3rd-degree corruption networks in Neo4j.

**Architecture:** Python workers handle the ETL process. Specific `gatherers` for transactional APIs (real-time/daily pull) and `loaders` for massive batch dumps (CSV/ZIP). Data is pushed to Spring Boot REST endpoints or directly loaded into Neo4j using the neo4j python driver.

**Tech Stack:** Python (Requests, Streaming CSV I/O), Neo4j Python Driver, Spring Boot API (destination).

---

### Task 1: Foundation — API Client Classes ✅

**Files:**
- Modify: `workers/src/core/api_client.py`
- Create: `workers/tests/test_api_client.py`

Added `PortalTransparenciaClient` with API key auth, rate limiting, and empty param filtering.

---

### Task 2: Transactional Gatherer — Portal da Transparência ✅

**Files:**
- Expanded: `workers/src/gatherers/transparencia_gatherer.py`

Full implementation covering:
- Remuneração de servidores (CPF)
- Servidores por órgão
- Contratos federais por CNPJ
- Licitações por CNPJ
- Despesas por favorecido
- Cross-reference engine

---

### Task 3: Transactional Gatherer — Brasil API CNPJ ✅

**Files:**
- Create: `workers/src/gatherers/brasil_api_gatherer.py`

Features:
- Consulta QSA completo via BrasilAPI
- Extração de sócios/administradores
- Batch lookup com rate limiting
- Conversão para nós/edges Neo4j

---

### Task 4: Transactional Gatherer — Querido Diário OKBR ✅

**Files:**
- Create: `workers/src/gatherers/querido_diario_gatherer.py`

Features:
- Busca por texto em Diários Oficiais municipais
- Busca por CNPJ e nome de pessoa
- Cross-check de suspeitos (CNPJ + nomes)
- Paginação automática

---

### Task 5: Batch Loader — TSE Campaign Donations ✅

**Files:**
- Create: `workers/src/loaders/tse_batch_loader.py`

Features:
- Download de dumps ZIP do TSE por ano
- Parser de CSV de receitas de campanha (doações)
- Parser de CSV de declaração de bens
- Cross-check de doadores com folha de pagamento (rachadinha detector)
- Ingestão Neo4j batch

---

### Task 6: Batch Loader — DataJud CNJ ✅

**Files:**
- Create: `workers/src/loaders/datajud_loader.py`

Features:
- Busca em todos os tribunais (TRF1-5, STF, STJ, TST)
- Filtragem por classes de improbidade administrativa
- Score de risco judicial (0-100)
- Lookup por nome e CPF/CNPJ

---

### Task 7: Batch Loader — Receita Federal QSA (Full Production) ✅

**Files:**
- Expanded: `workers/src/loaders/rfb_cnpj_loader.py`

Features:
- Download particionado (10 partições)
- Streaming CSV line-by-line (sem carregar na memória)
- Batched Neo4j UNWIND (1000 registros por batch)
- Parser para Empresas e Sócios
- Backward-compatible com testes existentes

---

### Task 8: Cross-Match Orchestrator ✅

**Files:**
- Create: `workers/src/gatherers/cross_match_orchestrator.py`

Pipeline de 7 steps:
1. Fetch deputies (Câmara API)
2. Extract suspect CNPJs from CEAP expenses
3. Lookup QSA via Brasil API
4. Check federal contracts (Portal da Transparência)
5. Search Official Gazettes (Querido Diário)
6. Check judicial records (DataJud)
7. Ingest to Neo4j + compute composite risk score

---

## Verification

### Dry-Run Results ✅
- Orchestrator processed 10 deputies end-to-end
- 5 live APIs called successfully
- Composite risk scores computed
- Top risk: Aguinaldo Ribeiro (PP-PB) at 20/100
- Results saved to `/tmp/cross_match_results.json`
