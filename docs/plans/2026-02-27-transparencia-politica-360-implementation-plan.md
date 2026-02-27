# Transparência Política 360 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the core Java Spring Boot backend and the async Python NLP workers for crossing political data.

**Architecture:** The system will use a PostgreSQL database. Python workers will ingest data from public APIs and NLP process it, communicating with the Java backend via synchronous REST APIs.

**Tech Stack:** Java 21, Spring Boot 3.x, Python 3.11, PostgreSQL.

## User Review Required
> [!IMPORTANT]
> Please review the architecture approach. Once approved, we can proceed with execution.

## Proposed Changes

### Java Spring Boot Core

#### [NEW] `backend/build.gradle` (or `pom.xml`)
Initialize the Spring Boot project with Web, Data JPA, PostgreSQL Driver, and Validation.

#### [NEW] `backend/src/main/resources/application.yml`
Configure PostgreSQL connection and basic properties.

#### [NEW] `backend/src/main/java/com/tp360/core/domain/Politician.java`
Entity representing a politician.

#### [NEW] `backend/src/main/java/com/tp360/core/domain/Promise.java`
Entity representing a campaign promise.

#### [NEW] `backend/src/main/java/com/tp360/core/domain/Vote.java`
Entity representing a plenary vote.

#### [NEW] `backend/src/main/java/com/tp360/core/controller/WorkerIntegrationController.java`
REST API for Python workers to POST ingested data and NLP results.

### Python NLP Workers

#### [NEW] `workers/requirements.txt`
Setup python dependencies: `requests`, `pandas`, `pydantic`, `openai` (or other LLM client).

#### [NEW] `workers/src/gatherers/camara_gatherer.py`
Worker that pulls data from `dadosabertos.camara.leg.br` and pushes to Spring Boot.

#### [NEW] `workers/src/gatherers/senado_gatherer.py`
Worker that pulls data from `legis.senado.leg.br` and pushes to Spring Boot.

#### [NEW] `workers/src/nlp/coherence_worker.py`
Worker that pulls Votes and Promises from Spring Boot, evaluates using LLM, and pushes the Coherence Score back.

---

## Task Breakdown

### Task 1: Spring Boot Core Setup
**Files:**
- Create: `backend/build.gradle`
- Create: `backend/src/main/resources/application.yml`
- Create: `backend/src/main/java/com/tp360/core/CoreApplication.java`

**Step 1:** Initialize Spring Boot application with standard folder structure.
**Step 2:** Configure `application.yml` for PostgreSQL.
**Step 3:** Commit the base project.

### Task 2: Core Domain Entities
**Files:**
- Create: `backend/src/main/java/com/tp360/core/domain/Politician.java`
- Create: `backend/src/main/java/com/tp360/core/domain/Promise.java`
- Create: `backend/src/main/java/com/tp360/core/domain/Vote.java`
- Create: `backend/src/main/java/com/tp360/core/repository/*.java`

**Step 1:** Write JPA entities mapping the core tables.
**Step 2:** Create corresponding Spring Data Repositories.
**Step 3:** Commit domain layer.

### Task 3: Worker Integration REST APIs
**Files:**
- Create: `backend/src/main/java/com/tp360/core/controller/WorkerIntegrationController.java`
- Create: `backend/src/main/java/com/tp360/core/service/DataIngestionService.java`

**Step 1:** Create endpoints like `POST /api/internal/workers/ingest/politician`.
**Step 2:** Write tests utilizing `@WebMvcTest` to verify worker endpoints.
**Step 3:** Commit the API layer.

### Task 4: Python Workers Environment Setup
**Files:**
- Create: `workers/requirements.txt`
- Create: `workers/src/core/api_client.py`

**Step 1:** Define requirements and basic API client for talking to Spring Boot.
**Step 2:** Commit worker setup.

### Task 5: Implement Câmara Gatherer
**Files:**
- Create: `workers/src/gatherers/camara_gatherer.py`

**Step 1:** Implement GET requests to target REST endpoints handling pagination and rate limiting.
**Step 2:** POST the fetched data structured via Pydantic to the Spring Boot REST API.
**Step 3:** Commit Gatherer.

## Verification Plan

### Automated Tests
- Java Core: Run `./gradlew test` (or `./mvnw test`) to verify all JPA persistence and REST controllers via `@DataJpaTest` and `@WebMvcTest`.
- Python Workers: Use `pytest` to run isolated unit tests mocking external API calls (`responses` library) to ensure parsing and data structure formatting before pushing to Java.

### Manual Verification
- Start the PostgreSQL database via Docker.
- Start the Spring Boot application locally (`./gradlew bootRun`).
- Execute a Python gatherer script (`python workers/src/gatherers/camara_gatherer.py`).
- Verify if the data successfully lands on PostgreSQL by querying the database.
