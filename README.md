# 🛡️ Transparência 360 — Auditoria Pública Inteligente

<p align="center">
  <strong>Plataforma OSINT que cruza dados de 10+ APIs governamentais para detectar anomalias patrimoniais, rachadinhas e desvio de emendas parlamentares.</strong>
</p>

<p align="center">
  <img alt="Java" src="https://img.shields.io/badge/Java-17-orange?style=flat-square&logo=openjdk"/>
  <img alt="Spring Boot" src="https://img.shields.io/badge/Spring_Boot-3.2-green?style=flat-square&logo=springboot"/>
  <img alt="React" src="https://img.shields.io/badge/React-19-blue?style=flat-square&logo=react"/>
  <img alt="Neo4j" src="https://img.shields.io/badge/Neo4j-5.26-blue?style=flat-square&logo=neo4j"/>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-yellow?style=flat-square&logo=python"/>
  <img alt="License" src="https://img.shields.io/badge/Dados-Públicos_(LAI)-lightgrey?style=flat-square"/>
</p>

---

## 📑 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Pré-Requisitos](#-pré-requisitos)
- [Guia de Instalação Completo](#-guia-de-instalação-completo)
  - [1. Clonar o Repositório](#1-clonar-o-repositório)
  - [2. Infraestrutura (Docker)](#2-infraestrutura-docker)
  - [3. Backend (Spring Boot)](#3-backend-spring-boot)
  - [4. Frontend (Vite + React)](#4-frontend-vite--react)
  - [5. Pipeline de Extração (Python)](#5-pipeline-de-extração-python)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Modos de Execução](#-modos-de-execução)
- [Estrutura de Pastas](#-estrutura-de-pastas)
- [O que o Pipeline faz?](#-o-que-o-pipeline-faz)
- [Fontes de Dados](#-fontes-de-dados)
- [Verificação Rápida (Smoke Test)](#-verificação-rápida-smoke-test)
- [Troubleshooting](#-troubleshooting)
- [Como Contribuir](#-como-contribuir)

---

## 🔍 Visão Geral

O **Transparência 360** é um radar de irregularidades que consome APIs públicas brasileiras (Câmara, Portal da Transparência, TSE, DataJud, Querido Diário, PNCP, Receita Federal, TCU) e aplica algoritmos de cruzamento para detectar:

| Módulo | O que detecta |
|:---|:---|
| 🕵️ **Rachadinha Scoring** | Assessores que devolvem salário ao político (cruzamento gabinete × doadores × fornecedores) |
| 📈 **Anomalia Patrimonial** | Crescimento incompatível do patrimônio declarado (TSE 2014→2018→2022) |
| 🏢 **Empresas Fantasma** | Fornecedores recém-criados, sem funcionários, que recebem CEAP |
| 🌐 **Teletransporte** | Despesas em cidade X no mesmo dia de presença registrada em Brasília |
| 💸 **Ciclo das Emendas Pix** | Emenda → Prefeitura → Licitação → Empresa do doador de campanha |
| 📰 **NLP Diários Oficiais** | Dispensas de licitação suspeitas em diários municipais (Querido Diário) |
| ⚖️ **Risco Judiciário** | Processos de improbidade administrativa (DataJud/CNJ) |
| 🏛️ **TCU** | Contas julgadas irregulares pelo Tribunal de Contas da União |

---

## 🏗️ Arquitetura do Sistema

```
┌──────────────────────────────────────────────────────────────────┐
│                        TRANSPARÊNCIA 360                        │
├──────────────┬──────────────────┬────────────────────────────────┤
│   Frontend   │     Backend      │     Workers (Python)           │
│  Vite+React  │  Spring Boot     │  Pipeline de 26 etapas         │
│  :5173       │  :8080           │  (Extração + Análise + ML)     │
│              │                  │                                │
│  • Dashboard │  • REST API      │  • APIs Governamentais         │
│  • Grafos    │  • Ingestão      │  • Dumps TSE/Receita Federal   │
│  • Tabelas   │  • Deduplicação  │  • NLP, Scoring, Cross-Match   │
├──────────────┴──────┬───────────┴────────────────────────────────┤
│                     │                                            │
│    PostgreSQL :5433 │  Neo4j :7687 (Bolt) / :7474 (HTTP)        │
│    (Relacional)     │  (Grafos: Follow The Money)                │
└─────────────────────┴────────────────────────────────────────────┘
```

---

## 📋 Pré-Requisitos

| Ferramenta | Versão Mínima | Para quê |
|:---|:---|:---|
| **Docker Desktop** | 4.x | PostgreSQL 15 + Neo4j 5.26 |
| **Java JDK** | 17 | Backend Spring Boot |
| **Node.js** | 18+ | Frontend Vite + React |
| **Python** | 3.10+ | Workers de extração e análise |
| **Git** | 2.x | Clonar o repositório |

> [!NOTE]
> No **Windows**, recomendamos rodar os comandos no **PowerShell** ou **Windows Terminal**.
> No **Linux/Mac**, use o terminal padrão.

---

## 🚀 Guia de Instalação Completo

### 1. Clonar o Repositório

```bash
git clone https://github.com/MatheusMarkies/Transparencia-360.git
cd Transparencia-360
```

---

### 2. Infraestrutura (Docker)

Suba os bancos de dados com Docker Compose:

```bash
docker-compose up -d
```

Isso cria dois containers:

| Serviço | Container | Porta Local | Credenciais |
|:---|:---|:---|:---|
| **PostgreSQL 15** | `tp360-db` | `5433` | `postgres` / `password` / DB: `tp360` |
| **Neo4j 5.26** | `tp360-neo4j` | `7474` (HTTP) / `7687` (Bolt) | `neo4j` / `admin123` |

**Verificar se estão rodando:**
```bash
docker ps
```

**Acessar o Neo4j Browser:**
Abra [http://localhost:7474](http://localhost:7474) e faça login com `neo4j` / `admin123`.

> [!WARNING]
> A porta do PostgreSQL é **5433** (não a padrão 5432). Isso evita conflitos se você já tem um Postgres local instalado.

---

### 3. Backend (Spring Boot)

```bash
cd backend
```

**Linux / Mac:**
```bash
./gradlew bootRun
```

**Windows (PowerShell):**
```powershell
.\gradlew.bat bootRun
```

O backend sobe na porta **8080**. Aguarde a mensagem `Started Tp360Application` no console.

**Verificar se está online:**
```bash
curl http://localhost:8080/api/v1/politicians/search?name=
# Deve retornar [] (lista vazia antes da extração)
```

> [!TIP]
> **Modo Dev (sem Docker):** Se não quiser subir o Docker, use o perfil `dev` que usa H2 (banco em memória):
> ```bash
> ./gradlew bootRun --args='--spring.profiles.active=dev'
> ```
> ⚠️ O modo dev **desabilita o Neo4j**, então os grafos e emendas não funcionarão.

---

### 4. Frontend (Vite + React)

Abra um **novo terminal**:

```bash
cd frontend
npm install
npm run dev
```

O frontend sobe em [http://localhost:5173](http://localhost:5173).

> [!NOTE]
> O frontend se conecta ao backend em `http://localhost:8080`. Para alterar, edite a constante `BACKEND_URL` em `src/App.tsx`.

---

### 5. Pipeline de Extração (Python)

O pipeline de extração é o coração do sistema — ele alimenta o backend com dados reais das APIs públicas.

#### 5.1 Instalar Dependências

```bash
cd workers
pip install -r requirements.txt
```

**Dependências principais:**
- `requests` — Chamadas HTTP para APIs governamentais
- `httpx` — Cliente HTTP assíncrono (APIs da Câmara e Portal)
- `polars` / `pandas` — Processamento de dados tabulares
- `duckdb` — Queries analíticas locais em Parquet
- `spacy` — NLP para análise de Diários Oficiais
- `PyMuPDF` — Extração de texto de PDFs (notas fiscais)

#### 5.2 Configurar Variáveis de Ambiente

```powershell
# Windows PowerShell
$env:PORTAL_API_KEY = "SUA_CHAVE_AQUI"
```

```bash
# Linux / Mac
export PORTAL_API_KEY="SUA_CHAVE_AQUI"
```

> [!IMPORTANT]
> A **API Key do Portal da Transparência** é **obrigatória** para acessar dados de emendas, servidores e contratos.
> Solicite gratuitamente em: https://portaldatransparencia.gov.br/api-de-dados

#### 5.3 Executar o Pipeline

**Execução rápida (15 deputados — ideal para teste):**
```bash
python run_all_extractions.py --limit 15
```

**Execução completa (todos os 513 deputados):**
```bash
python run_all_extractions.py --limit 513
```

**Re-executar apenas as análises (sem resetar o banco):**
```bash
python run_all_extractions.py --limit 15 --keep-db
```

> [!TIP]
> O flag `--keep-db` pula as Fases 1 e 2 (download + ingestão) e executa apenas a Fase 3 (análises, scoring, grafos). Isso é muito útil quando você já tem os dados no banco e quer apenas recalcular os scores ou rodar um novo worker.

---

## 🔐 Variáveis de Ambiente

| Variável | Obrigatória | Onde obter | Usada por |
|:---|:---|:---|:---|
| `PORTAL_API_KEY` | ✅ Sim | [Portal da Transparência](https://portaldatransparencia.gov.br/api-de-dados) | Workers (emendas, servidores, contratos) |
| `NEO4J_URI` | Não (default: `bolt://localhost:7687`) | Docker Compose | Workers (reset do banco de grafos) |
| `NEO4J_USER` | Não (default: `neo4j`) | Docker Compose | Workers |
| `NEO4J_PASSWORD` | Não (default: `admin123`) | Docker Compose | Workers |

---

## ⚙️ Modos de Execução

| Modo | Comando | Backend | Frontend | Banco de Dados |
|:---|:---|:---|:---|:---|
| **Produção (Full)** | `docker-compose up -d` + `gradlew bootRun` | Spring Boot | Vite | PostgreSQL + Neo4j |
| **Dev (Sem Docker)** | `gradlew bootRun --args='--spring.profiles.active=dev'` | Spring Boot | Vite | H2 (memória) |
| **Pipeline Completo** | `python run_all_extractions.py --limit N` | Precisa estar rodando | — | PostgreSQL + Neo4j |
| **Pipeline Parcial** | `python run_all_extractions.py --limit N --keep-db` | Precisa estar rodando | — | Dados existentes |

---

## 📁 Estrutura de Pastas

```
Transparencia-360/
│
├── backend/                          # API REST (Spring Boot 3.2 + Java 17)
│   ├── src/main/java/com/tp360/
│   │   ├── core/controller/          # Endpoints REST (Search, Graph, Worker Integration)
│   │   ├── core/domain/              # Entidades JPA (Politician, Vote, Promise)
│   │   ├── core/entities/neo4j/      # Nós do Neo4j (PoliticoNode, DespesaNode)
│   │   ├── core/repositories/neo4j/  # Queries Cypher (Triangulação, Follow The Money)
│   │   ├── core/service/             # Lógica de Negócio (Ingestão, Deduplicação)
│   │   └── core/dto/                 # DTOs para o Frontend
│   ├── src/main/resources/
│   │   ├── application.yml           # Config Produção (PostgreSQL + Neo4j)
│   │   └── application-dev.yml       # Config Dev (H2, sem Neo4j)
│   └── build.gradle                  # Dependências Gradle
│
├── frontend/                         # Dashboard Interativo (Vite 7 + React 19)
│   ├── src/
│   │   ├── App.tsx                   # Componente principal (Search, Tabs, Grafos)
│   │   └── components/               # Componentes reutilizáveis
│   │       ├── RadarRisco.tsx        # Radar circular de probabilidade de fraude
│   │       ├── Dossie/               # Ranking Table, Politician Card
│   │       ├── Patrimonio/           # Gráfico de evolução patrimonial
│   │       └── Rastreabilidade/      # Tags de fonte e badges de confiança
│   └── package.json
│
├── workers/                          # Pipeline de Extração (Python 3.10+)
│   ├── run_all_extractions.py        # Orquestrador principal (26 etapas)
│   ├── ingest_parquet.py             # Ingestão de Parquet para a API
│   ├── requirements.txt              # Dependências Python
│   └── src/gatherers/                # Workers individuais
│       ├── camara_gatherer.py        # Câmara dos Deputados (base data)
│       ├── expenses_worker.py        # Despesas CEAP
│       ├── absences_worker.py        # Presenças no plenário
│       ├── emendas_gatherer.py       # Emendas parlamentares
│       ├── rachadinha_worker.py      # Motor de Scoring (ML)
│       ├── staff_anomaly_worker.py   # Anomalias de pessoal
│       ├── wealth_anomaly_worker.py  # Anomalia patrimonial
│       ├── ghost_employee_worker.py  # Funcionários fantasma
│       ├── spatial_anomaly_worker.py # Teletransporte
│       ├── querido_diario_gatherer.py # NLP Diários Oficiais
│       ├── tcu_worker.py             # TCU (contas irregulares)
│       ├── pncp_worker.py            # Licitações PNCP
│       ├── super_report_worker.py    # Gerador de Laudo JSON unificado
│       └── ...                       # + outros 14 workers especializados
│
├── extractors/                       # Extractors de APIs (Async + Polars)
│   ├── camara_deputados.py           # CEAP + Presenças
│   ├── portal_transparencia.py       # Emendas + Servidores
│   └── querido_diario.py             # Diários Oficiais municipais
│
├── etl/                              # ETL de dumps massivos
│   ├── tse.py                        # Doações + Bens declarados
│   └── receita_federal.py            # QSA (Sócios) + Empresas
│
├── data/                             # Dados baixados e processados
│   ├── downloads/                    # Arquivos brutos das APIs
│   └── processed/                    # Parquet limpo + Super Reports
│
├── docs/plans/                       # Planos arquiteturais por módulo
├── docker-compose.yml                # PostgreSQL 15 + Neo4j 5.26
├── ARQUITETURA_PIPELINE.md           # Documentação técnica completa
├── DATA_SOURCES.md                   # Dicionário de APIs e fontes
└── ROADMAP.md                        # Roadmap de evolução
```

---

## 🔬 O que o Pipeline faz?

O script `run_all_extractions.py` executa **26 etapas** organizadas em 3 fases:

### Fase 1 — Extração de Dados (Download)
Consome APIs públicas em paralelo e salva os dados brutos no disco.

| Etapa | Worker | Fonte |
|:---|:---|:---|
| 1 | `CamaraGatherer` | Câmara dos Deputados (dados base) |
| 2 | `CamaraExtractors` | CEAP + Presenças (assíncrono) |
| 3 | `PortalTransparência` | Emendas + Servidores (assíncrono) |
| 7 | `TSE ETL` | Doações e Bens (2014, 2018, 2022) |
| 22 | `Receita Federal ETL` | QSA (Sócios) + Empresas |

### Fase 2 — Ingestão e Limpeza
Carrega dados no PostgreSQL/Neo4j, deduplicando registros.

| Etapa | Worker | Função |
|:---|:---|:---|
| 4-5 | `ExpensesWorker` / `AbsencesWorker` | Despesas e presenças |
| 6 | `Ingestão Parquet` | Carga bulk de Parquet → API |
| 19 | `Deduplicação` | Remove duplicatas no backend |

### Fase 3 — Análise e Enriquecimento (executa sempre, mesmo com `--keep-db`)

| Etapa | Worker | O que detecta |
|:---|:---|:---|
| 8 | `CamaraCabinetScraper` | Raspa lista de funcionários do gabinete |
| 9 | `TSE Worker` | Match TSE ↔ Deputados (patrimônio) |
| 10 | `CrossMatchOrchestrator` | Cruza assessores × fornecedores × doadores |
| 11 | `WealthAnomalyWorker` | Crescimento incompatível do patrimônio |
| 12 | `GhostEmployeeWorker` | Funcionários fantasma |
| 13 | `StaffAnomalyWorker` | Anomalias de contratação |
| 14 | `SpatialAnomalyWorker` | Detector de Teletransporte |
| 15 | `RachadinhaWorker` | Motor de Scoring ML |
| 16 | `EmendasGatherer` | Emendas parlamentares (multi-ano) |
| 17 | `EmendasPixWorker` | Ciclo das Emendas Pix (Follow The Money) |
| 18 | `NLP Gazette` | Diários Oficiais (Querido Diário) |
| 20 | `CamaraNLP` | Coerência de Voto (NLP) |
| 21 | `PNCP` | Licitações públicas |
| 23 | `JudicialAggregator` | Processos de improbidade (DataJud) |
| 24 | `TCU Worker` | Contas irregulares |
| 25 | `Pruning` | Remove registros fantasma do banco |
| 26 | `SuperReportWorker` | Gera laudo JSON unificado de auditoria |

### Relatórios Gerados (Super Reports)

A última etapa do pipeline (`SuperReportWorker`) gera um **dossiê JSON completo** para cada político processado. Esses arquivos ficam salvos em:

```
workers/data/processed/super_reports/
├── super_report_alberto_fraga_camara_73579.json
├── super_report_alice_portugal_camara_74057.json
├── super_report_...
```

Cada JSON contém **4 seções**:

| Seção | O que contém |
|:---|:---|
| `01_metadados` | Nome, partido, estado, ID da Câmara, data de extração |
| `02_documentos_lidos_e_grafos` | Quantos nós foram processados no Neo4j (despesas, empresas, emendas, promessas, votos) |
| `03_estatisticas_patrimoniais` | Total gasto na CEAP, taxa de ausência, patrimônio declarado ao TSE, fator de anomalia |
| `04_alertas_de_inteligencia` | Score de rachadinha (0-100) com evidências detalhadas por heurística, anomalias de gabinete, teletransporte espacial, menções em diários oficiais, processos judiciais |

> [!TIP]
> Os Super Reports são a forma mais fácil de **auditar os resultados** do pipeline. Abra qualquer JSON na pasta e confira se os dados batem com as fontes oficiais.



## 🗃️ Fontes de Dados

| Fonte | Tipo | API Key? | Documentação |
|:---|:---|:---|:---|
| Câmara dos Deputados | REST API | ❌ | [Swagger](https://dadosabertos.camara.leg.br/swagger/api.html) |
| Portal da Transparência (CGU) | REST API | ✅ | [Swagger](https://api.portaldatransparencia.gov.br/swagger-ui.html) |
| TSE (Dados Eleitorais) | Dumps CSV | ❌ | [Portal TSE](https://dadosabertos.tse.jus.br/) |
| Receita Federal (CNPJs) | Dumps CSV | ❌ | [dados.gov.br](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj) |
| Querido Diário (OKBR) | REST API | ❌ | [Docs](https://docs.queridodiario.ok.org.br/) |
| DataJud (CNJ) | REST API | ❌ | [Wiki](https://datajud-wiki.cnj.jus.br/api-publica/) |
| PNCP | REST API | ❌ | [Swagger](https://pncp.gov.br/app/api) |
| TCU | REST/Dumps | ❌ | [Portal TCU](https://dadosabertos.tcu.gov.br/) |
| BrasilAPI | REST API | ❌ | [Docs](https://brasilapi.com.br/docs) |

---

## ✅ Verificação Rápida (Smoke Test)

Depois de subir tudo, verifique se os serviços estão funcionando:

```powershell
# 1. Docker (bancos de dados)
docker ps
# Esperado: tp360-db (healthy) e tp360-neo4j (healthy)

# 2. Backend
curl http://localhost:8080/api/v1/politicians/search?name=
# Esperado: [] ou lista de políticos

# 3. Frontend
# Abra http://localhost:5173 no navegador
# Esperado: Dashboard com barra de pesquisa e ranking

# 4. Neo4j Browser
# Abra http://localhost:7474
# Esperado: Interface web do Neo4j
```

Após rodar o pipeline:
```powershell
# Verificar se os dados foram ingeridos
curl http://localhost:8080/api/v1/politicians/search?name=
# Esperado: Lista com N políticos (conforme --limit)

# Verificar o grafo de um político (substitua {id})
curl http://localhost:8080/api/v1/politicians/1/graph
# Esperado: JSON com nodes e links
```

---

## 🛠️ Troubleshooting

<details>
<summary><strong>Docker: Container não sobe ou fica "unhealthy"</strong></summary>

```bash
# Ver logs do container
docker logs tp360-db
docker logs tp360-neo4j

# Restart forçado
docker-compose down -v && docker-compose up -d
```
> O `-v` remove os volumes (apaga dados dos bancos). Use com cuidado.
</details>

<details>
<summary><strong>Backend: Erro de conexão com PostgreSQL</strong></summary>

Verifique se a porta **5433** está correta no `application.yml`:
```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5433/tp360
```
Se estiver rodando o Postgres fora do Docker (porta 5432), ajuste a porta.
</details>

<details>
<summary><strong>Backend: Erro de conexão com Neo4j</strong></summary>

Se estiver rodando **fora** do Docker, o URI padrão no `application.yml` é `bolt://neo4j:7687` (nome do container). Mude para:
```yaml
spring:
  neo4j:
    uri: bolt://localhost:7687
```
</details>

<details>
<summary><strong>Frontend: Erro de CORS ou conexão recusada</strong></summary>

O backend aceita origens de `localhost:5173`, `5174` e `3000`. Se você alterou a porta do Vite, adicione a nova origem em `FrontendSearchController.java`:
```java
@CrossOrigin(origins = { "http://localhost:5173", "http://localhost:NOVA_PORTA" })
```
</details>

<details>
<summary><strong>Workers: "PORTAL_API_KEY not set"</strong></summary>

A variável precisa estar definida **no mesmo terminal** onde você roda o pipeline:
```powershell
# PowerShell (temporária — vale só para esta sessão)
$env:PORTAL_API_KEY = "SUA_CHAVE"

# Para tornar permanente no Windows:
[System.Environment]::SetEnvironmentVariable("PORTAL_API_KEY", "SUA_CHAVE", "User")
```
</details>

<details>
<summary><strong>Workers: "ModuleNotFoundError" (spacy, polars, etc.)</strong></summary>

```bash
cd workers
pip install -r requirements.txt

# Se usar spacy para NLP:
python -m spacy download pt_core_news_sm
```
</details>

---

## 🤝 Como Contribuir

1. **Leia o [ROADMAP.md](ROADMAP.md)** — escolha uma das frentes abertas
2. **Entenda a arquitetura** — leia o [ARQUITETURA_PIPELINE.md](ARQUITETURA_PIPELINE.md)
3. **Consulte as fontes** — veja o [DATA_SOURCES.md](DATA_SOURCES.md)
4. **Clone, crie uma branch, e mande um PR**

### Áreas que mais precisam de ajuda:

| Área | Skill | Descrição |
|:---|:---|:---|
| **Frontend** | React + TypeScript | Novos componentes (Timeline, mapas, filtros avançados) |
| **Backend** | Java + Spring Boot | Novos endpoints, queries Cypher otimizadas |
| **Workers** | Python + NLP/ML | Novos detectores de fraude, melhorias de scoring |
| **Infra** | Docker + CI/CD | Pipeline de deploy, testes automatizados |
| **Dados** | Polars + DuckDB | Otimização de processamento de dumps massivos |

---

**⚠️ Aviso Legal:** Este sistema utiliza **exclusivamente** APIs Públicas e Dados Abertos protegidos pela **Lei de Acesso à Informação (LAI)**. Nenhum dado privado ou sigiloso é coletado ou armazenado.

**© 2026** — Dados públicos para vigilância cidadã.
