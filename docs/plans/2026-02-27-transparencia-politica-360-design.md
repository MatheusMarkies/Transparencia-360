# Transparência Política 360 - Design Document

## 1. Overview
The "Transparência Política 360" platform is an intelligence (OSINT) and NLP system focused on monitoring the performance, expenditures, and coherence of Brazilian politicians. It gathers public data, processes the information, cross-references campaign promises with plenary votes using LLMs, and displays the results in a Knowledge Graph and a fast search frontend.

## 2. Architecture Approach
The system follows a completely asynchronous NLP pipeline architecture with separated concerns:
- **Core Backend**: Built in Java with Spring Boot 3.x (Clean Architecture, SOLID principles). Acts as the central orchestrator and state manager for the processing queues.
- **Workers**: Python 3.11+ workers highly specialized in data ingestion, extraction, and natural language processing.
- **Database**: Single unified PostgreSQL database handling both transactional and graph-like relational structures efficiently.

### 2.1 Communication Protocol
The architecture utilizes **Synchronous REST APIs** for the communication between Python workers and the Java core. The workers pull tasks (e.g., pending files) via GET APIs and push structured data and NLP analysis back via POST APIs. This allows the backend to control the rate limits and maintain data consistency.

### 2.2 Worker Topology
1. **Data Gatherers**: Ingests raw data from Câmara dos Deputados, Senado Federal, Portal da Transparência, and TSE APIs. Pushes raw structured responses to the Core Backend.
2. **NLP Workers**: Periodically queries the Core Backend for unprocessed documents (ex: government plan PDFs). Extracts text, identifies promises, and sends structured promises back to the Core via REST.
3. **Cross-Reference Workers**: Consumes recent votes and extracted promises from the Core Backend. Evaluates coherence using LLMs. Sends the coherence score and mapped knowledge graph links (Vote-Promise) to the Core Backend.

## 3. Technology Stack
- **Backend**: Java / Spring Boot 3.x (Spring Web, Spring Data JPA, Spring Security).
- **Data Pipeline**: Python 3.11+ (typing, requests, pandas).
- **Persistence**: PostgreSQL (acting as relational and scalable backing for knowledge graph entities).

## 4. Key Considerations
- **High Performance & Scalability**: Spring Boot serves compiled and pre-processed NLP results fast to the frontend.
- **Resilience**: Workers operate independently. Failures in one NLP worker do not compromise the web traffic on the Spring Boot API.
- **Cost Management**: LLM token consumption is predictable and asynchronous, managed by backend job dispatching instead of unstructured on-the-fly user requests.
