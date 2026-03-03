# 🏗️ Arquitetura Completa do Pipeline de Dados — Transparência 360

> **Para quem está chegando agora:** Este documento explica como o sistema funciona por dentro, desde a coleta de dados até a exibição no dashboard. Se você nunca viu código antes, leia as caixas "🧑‍🔧 Explicação Simples" que aparecem ao longo do texto. Se você é desenvolvedor, veja os detalhes técnicos.

---

## 1. Visão Geral da Arquitetura

O Transparência 360 tem **3 grandes peças** que trabalham juntas:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRANSPARÊNCIA 360                                  │
│                                                                            │
│   ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────┐ │
│   │   Frontend    │    │    Backend        │    │  Workers (Python)        │ │
│   │  Vite+React   │◄──►│  Spring Boot     │◄──►│  Pipeline de 26 etapas   │ │
│   │  :5173        │    │  :8080           │    │                          │ │
│   │               │    │                  │    │  • Coleta de dados       │ │
│   │  O que o      │    │  O "cérebro"     │    │  • Análises de risco     │ │ 
│   │  usuário vê   │    │  que organiza    │    │  • Construção de grafos  │ │
│   │  (dashboard)  │    │  tudo            │    │  • NLP em documentos     │ │
│   └──────────────┘    └────────┬─────────┘    └──────────────────────────┘ │
│                                │                                           │
│                    ┌───────────┴───────────┐                               │
│                    │                       │                               │
│              ┌─────┴──────┐    ┌───────────┴──────┐                        │
│              │ PostgreSQL │    │     Neo4j         │                        │
│              │    :5433   │    │  :7474 / :7687    │                        │
│              │            │    │                   │                        │
│              │ Dados dos  │    │ Grafos: quem      │                        │
│              │ políticos  │    │ pagou quem,       │                        │
│              │ (tabelas)  │    │ fluxo do dinheiro │                        │
│              └────────────┘    └───────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

> 🧑‍🔧 **Explicação Simples:** Imagine uma equipe de detetives. Os **Workers** são os "investigadores de campo" que vão atrás dos dados nas fontes públicas. O **Backend** é o "delegado" que recebe as provas, organiza e guarda (em dois cofres: PostgreSQL para dados tabulares e Neo4j para mapas de conexões). O **Frontend** é o "painel da delegacia" onde qualquer cidadão pode ver o resultado da investigação.

---

## 2. Os Dois Bancos de Dados

### 2.1 PostgreSQL (Banco Relacional) — `:5433`

Armazena os dados estruturados dos políticos em tabelas tradicionais.

**O que está guardado aqui:**
- Dados pessoais: nome, partido, estado, cargo, foto
- Patrimônio declarado ao TSE (2014, 2018, 2022)
- Total de despesas acumulado (CEAP)
- Scores de risco calculados (rachadinha, anomalia patrimonial, judiciário)
- Promessas de campanha e votos no plenário
- Contagem de ausências, proposições

**Entidades JPA (Java):**
| Classe Java | Tabela | O que guarda |
|:---|:---|:---|
| `Politician` | `politician` | Dados consolidados do parlamentar |
| `Promise` | `promise` | Promessas extraídas de discursos |
| `Vote` | `vote` | Votos nominais no plenário |

**Arquivo de configuração:** `backend/src/main/resources/application.yml`
```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5433/tp360
    username: postgres
    password: password
```

> 🧑‍🔧 **Explicação Simples:** O PostgreSQL é como uma planilha Excel gigante onde guardamos os dados de cada político em linhas e colunas. "Quanto ele gastou?", "Qual o patrimônio dele?" — tudo fica aqui.

### 2.2 Neo4j (Banco de Grafos) — `:7687` (dados) / `:7474` (interface web)

Armazena as **conexões entre entidades** — quem pagou quem, quem é sócio de quem, para qual prefeitura foi a emenda.

**Nós (Nodes) realmente implementados:**
| Nó | Propriedades | Criado por |
|:---|:---|:---|
| `Politico` | `id`, `name`, `party`, `state` | `DataIngestionService.upsertNeo4jPolitico()` |
| `Despesa` | `id`, `dataEmissao`, `nomeFornecedor`, `valorDocumento`, `categoria`, `ufFornecedor` | `DataIngestionService.ingestDespesa()` |
| `SessaoPlenario` | `id`, `data`, `tipo` | `DataIngestionService.ingestSessaoPlenario()` |
| `Municipio` | `codigoIbge` | `DataIngestionService.ingestEmendaPix()` |
| `Empresa` | `cnpj`, `name` | `DataIngestionService.ingestContratoMunicipal()` |
| `Pessoa` | `nome`, `cpfHash`, `fonte` | `DataIngestionService.ingestPessoaSocietaria()` |
| `DiarioOficial` | `url`, `territorio`, `data`, `score`, `cnpj_extraidos` | `GazetteNeo4jIngester` |
| `Licitacao` | `numero`, `modalidade` | `GazetteNeo4jIngester` |
| `Emenda` (via relacionamento `ENVIOU_EMENDA`) | `id`, `ano`, `valor`, `tipo` | `EmendasGatherer` |

**Relacionamentos realmente implementados:**
```
(:Politico)-[:GEROU_DESPESA]->(:Despesa)
(:Politico)-[:ESTEVE_PRESENTE_EM]->(:SessaoPlenario)
(:Politico)-[:ENVIOU_EMENDA {id, ano, valor, tipo}]->(:Municipio)
(:Municipio)-[:CONTRATOU {valor, modalidade}]->(:Empresa)
(:Empresa)-[:SOCIO_ADMINISTRADOR_DE]->(:Pessoa)
(:Pessoa)-[:DOOU_PARA_CAMPANHA]->(:Politico)
(:Empresa)-[:CITADA_EM]->(:DiarioOficial)
```

> 🧑‍🔧 **Explicação Simples:** O Neo4j é como um mapa de conexões. Imagine um quadro de barbante que você vê em filmes de detetive: "Este político pagou R$80.000 para esta empresa, cujo dono doou para a campanha do mesmo político". Esse tipo de rastreamento só é possível com um banco de grafos.

**O ciclo completo que estamos rastreando:**
```
Político ──(ENVIOU_EMENDA)──► Prefeitura ──(CONTRATOU)──► Empresa
    ▲                                                        │
    └───────────(DOOU_PARA_CAMPANHA)────── Sócio ◄──(SOCIO)──┘
```

---

## 3. O Pipeline de Extração (`run_all_extractions.py`)

O arquivo `workers/run_all_extractions.py` é o **orquestrador principal**. Ele executa **26 etapas** divididas em **3 fases**.

### Como rodar:
```bash
cd workers

# Execução rápida (10 deputados, ideal para teste)
python run_all_extractions.py --limit 10

# Execução completa (todos os 513 deputados)
python run_all_extractions.py --limit 513

# Recalcular apenas as análises (sem redownload)
python run_all_extractions.py --limit 30 --keep-db
```

> 🧑‍🔧 **Explicação Simples:** Esse é o "botão vermelho" do sistema. Quando você roda esse script, ele dispara uma série de robôs que vão buscar dados em sites do governo, calcular risks, montar grafos e gerar laudos. O `--limit` controla quantos políticos processar (comece com 10 para testar). O `--keep-db` pula as fases de download pesado e só roda as análises.

---

### FASE 0 — Setup e Reset dos Bancos

**O que acontece:**
1. Verifica/cria as pastas de dados (`data/downloads/`, `data/processed/`)
2. Se `--keep-db` NÃO foi passado:
   - Limpa todos os arquivos baixados anteriormente
   - Zera o Neo4j (`MATCH (n) DETACH DELETE n`)
   - Zera o PostgreSQL chamando `DELETE /api/internal/workers/ingest/reset-database`
3. Se `--keep-db` foi passado: só garante que as pastas existem, sem apagar nada.

**Arquivo:** `run_all_extractions.py` (linhas 69-119)

---

### FASE 1 — Extração de Dados (Downloads)

> Só executa se `--keep-db` NÃO foi passado.

Estes 4 passos rodam **em paralelo** (ao mesmo tempo) usando `ThreadPoolExecutor`:

#### Step 1: `CamaraGatherer` (Base Data)
**Script:** `workers/src/gatherers/camara_gatherer.py`
**O que faz:** Busca a lista de deputados na API da Câmara e envia cada um para o backend via `POST /api/internal/workers/ingest/politician`.

> 🧑‍🔧 **Explicação Simples:** É o primeiro passo — descobre quem são os deputados em exercício e salva os dados de base (nome, partido, estado, foto).

#### Step 2: `Camara Extractors` (CEAP + Presenças)
**Script:** `extractors/camara_deputados.py`
**O que faz:** Baixa todas as notas fiscais da Cota Parlamentar (CEAP) e registros de presença no plenário e salva em formato `.parquet` no disco (`data/raw/camara/`).

**API usada:** `https://dadosabertos.camara.leg.br/api/v2`
- `GET /deputados/{id}/despesas?ano=YYYY` → Notas fiscais
- `GET /eventos?dataInicio=YYYY-MM-DD` → Presenças

> 🧑‍🔧 **Explicação Simples:** Baixa todas as "notinhas" de gastos dos deputados (passagens, restaurantes, escritórios) e o registro de quando eles estiveram (ou não) no plenário.

#### Step 3: `Portal Transparência Extractors`
**Script:** `extractors/portal_transparencia.py`
**O que faz:** Baixa as emendas parlamentares e a lista de servidores públicos do Portal da Transparência (CGU).

**API usada:** `https://api.portaldatransparencia.gov.br/api-de-dados`
- `GET /emendas-parlamentares?ano=YYYY` → Emendas Pix
- `GET /servidores?pagina=N` → Servidores (para cruzar com assessores)

**⚠️ Requer:** `PORTAL_API_KEY` (solicite em https://portaldatransparencia.gov.br/api-de-dados)

#### Step 7: `TSE ETL` (Eleições)
**Script:** `etl/tse.py`
**O que faz:** Processa os dumps massivos do TSE (doações de campanha e declaração de bens) para os anos de 2014, 2018 e 2022. Salva em `.parquet`.

> 🧑‍🔧 **Explicação Simples:** Lê os arquivos enormes do tribunal eleitoral para saber quanto cada político declarou ter de patrimônio e quem doou para as campanhas dele.

#### Step 22: `Receita Federal ETL` (QSA/Empresas)
**Script:** `etl/receita_federal.py`
**O que faz:** Processa os dumps gigantes da Receita Federal (Quadro de Sócios — QSA — e cadastro de empresas) usando Polars (processador de dados ultrarrápido escrito em Rust).

> 🧑‍🔧 **Explicação Simples:** Descobre quem é dono de cada empresa no Brasil. Isso é fundamental para detectar "laranjas" — quando o sócio de uma empresa contratada pelo político é parente dele.

---

### FASE 2 — Ingestão e Limpeza

> Só executa se `--keep-db` NÃO foi passado.

#### Step 4: `ExpensesWorker` (Legacy Sync)
**Script:** `workers/src/gatherers/expenses_worker.py`
**O que faz:** Busca despesas da Câmara API e envia para o backend via `POST /api/internal/workers/ingest/politician/{externalId}/despesa` — gravando tanto no PostgreSQL (total acumulado) quanto no Neo4j (cada nota individual como nó `Despesa`).

#### Step 5: `AbsencesWorker`
**Script:** `workers/src/gatherers/absences_worker.py`
**O que faz:** Busca presenças e ausências no plenário, ingerindo sessões no Neo4j via `POST /api/internal/workers/ingest/politician/{externalId}/sessao`.

#### Step 6: `Ingestão de Parquet`
**Script:** `workers/ingest_parquet.py`
**O que faz:** Lê os arquivos `.parquet` gerados na Fase 1 e os carrega em batch no backend via chamadas REST. É a fase mais pesada. Contém duas funções:
- `ingest_camara_despesas()` — Carrega despesas CEAP dos Parquets
- `ingest_emendas()` — Carrega emendas parlamentares

#### Step 19: `Backend Deduplication`
**O que faz:** Chama `POST /api/internal/workers/ingest/deduplicate` no backend para remover políticos duplicados. O algoritmo mantém o registro com mais campos preenchidos e mescla os dados dos duplicados no sobrevivente.

**Implementação do algoritmo (Java):** `DataIngestionService.deduplicatePoliticians()`
- Agrupa políticos por nome (case-insensitive)
- Para cada grupo com duplicatas, mantém o que tem mais campos não-nulos
- Mescla campos faltantes do duplicado no sobrevivente (sem sobrescrever dados existentes)
- Deleta as cópias

> 🧑‍🔧 **Explicação Simples:** Como os dados vêm de várias fontes diferentes, às vezes o mesmo político aparece mais de uma vez. Esse passo limpa essas repetições sem perder informação.

---

### FASE 3 — Análise, Enriquecimento e Grafos

> **Esta fase SEMPRE executa**, mesmo com `--keep-db`.

Os primeiros 4 passos rodam **em paralelo**:

#### Step 8: `WealthAnomalyWorker` (Anomalia Patrimonial)
**Script:** `workers/src/gatherers/wealth_anomaly_worker.py`
**O que faz:** Compara o patrimônio declarado ao TSE (2014 → 2018 → 2022) com o salário do deputado (R$44.000/mês). Se o crescimento patrimonial exceder o que seria possível poupando 100% do salário por 8 anos (R$2.102.400), levanta um alerta.
**Saída:** Atualiza o campo `wealthAnomalyDetails` do político no PostgreSQL.

> 🧑‍🔧 **Explicação Simples:** Se um deputado que ganha R$44 mil/mês declarou ao TSE que ficou R$5 milhões mais rico em 4 anos, algo não bate. Esse robô faz essa conta.

#### Step 9: `StaffAnomalyWorker` (Anomalia de Gabinete)
**Script:** `workers/src/gatherers/staff_anomaly_worker.py` (13.437 bytes — o maior worker)
**O que faz:**
1. Busca todas as despesas de cada deputado na API da Câmara
2. Agrega por fornecedor (total pago, número de notas)
3. Calcula estatísticas globais (média, desvio padrão, limiar de anomalia)
4. Usa **Isolation Forest** (algoritmo de Machine Learning) para identificar fornecedores com padrões atípicos
5. Marca alertas: `SUPER_PAGAMENTO` (acima do limiar) e `CONCENTRACAO` (fornecedor que só recebe deste deputado)
6. Salva relatório JSON em `data/processed/staff_anomalies/`

**Saída:** Atualiza `staffAnomalyCount` e `staffAnomalyDetails` no PostgreSQL.

> 🧑‍🔧 **Explicação Simples:** Analisa as "notas fiscais" do deputado e procura padrões estranhos — tipo uma empresa que recebeu R$80 mil de um só deputado, mas de nenhum outro. Ou um fornecedor com pagamentos muito fora da média. Usa inteligência artificial (Isolation Forest) para isso.

#### Step 11: `SpatialAnomalyWorker` (Teletransporte)
**Script:** `workers/src/gatherers/spatial_anomaly_worker.py`
**O que faz:** Consulta o Neo4j cruzando presenças no plenário com despesas do mesmo dia:
```cypher
MATCH (p:Politico)-[:ESTEVE_PRESENTE_EM]->(s:SessaoPlenario),
      (p)-[:GEROU_DESPESA]->(d:Despesa)
WHERE s.data = d.dataEmissao
      AND d.ufFornecedor <> 'DF'
      AND d.ufFornecedor <> 'NA'
RETURN ...
```
Se o deputado registrou presença em Brasília (DF) mas tem despesa emitida no mesmo dia em outro estado, isso é um "teletransporte".

> 🧑‍🔧 **Explicação Simples:** Se o deputado votou em Brasília na segunda-feira e tem uma nota fiscal de hotel em São Paulo no mesmo dia... ele se teletransportou? Esse robô encontra essas inconsistências.

#### Step 15: `CamaraNLPGatherer` (Download de Discursos)
**Script:** `workers/src/gatherers/camara_nlp_gatherer.py`
**O que faz:** Baixa os discursos parlamentares de cada deputado na API da Câmara para posterior análise de coerência (Step 16).

---

#### Step 10: `RachadinhaScoringWorker v2.0` (Motor de Risk Score)
**Script:** `workers/src/gatherers/rachadinha_worker.py` (31.659 bytes — **o maior arquivo do projeto**)

O coração do sistema. Calcula um **score de risco de 0 a 100** usando **5 heurísticas reais** (sem simulação):

| Heurística | Peso | O que analisa | API usada |
|:---|:---|:---|:---|
| **H1: Doador Compulsório** | 25 | Concentração de gastos com "Serviço de Pessoal" — assessores/prestadores que recebem muito podem estar devolvendo parte via doação | Câmara CEAP |
| **H2: Rotatividade de Laranjas** | 20 | Fornecedores que aparecem em apenas 1 ano e somem — pode indicar laranjas rotativos | Câmara CEAP (multi-ano) |
| **H3: Triangulação de CNPJs** | 25 | Busca fornecedores de consultoria/veículos e consulta o QSA (Quadro de Sócios) via Brasil API para fechar o ciclo | Câmara CEAP + BrasilAPI |
| **H4: NLP Gazette** | 15 | Busca CNPJs suspeitos em Diários Oficiais municipais via Querido Diário API | Querido Diário API |
| **H5: Judiciário** | 15 | Consulta DataJud (CNJ) por processos de improbidade administrativa contra o deputado | DataJud API (7 tribunais) |

**Saída:** Atualiza `cabinetRiskScore` e `cabinetRiskDetails` no PostgreSQL + salva JSON em `data/processed/rachadinha_reports/`.

> 🧑‍🔧 **Explicação Simples:** É o "detector de mentira" do sistema. Ele cruza 5 fontes diferentes para dar uma nota de risco para cada deputado. Se a nota é alta, existem padrões que merecem investigação. Se é baixa, o deputado parece transparente.

---

#### Step 12: `CrossMatchOrchestrator` (Neo4j Deep Graph Builder)
**Script:** `workers/src/gatherers/cross_match_orchestrator.py`

O **construtor do grafo profundo** no Neo4j. Executa 7 sub-etapas:

1. **Step 1:** Busca lista de deputados na Câmara API
2. **Step 2:** Analisa a CEAP de cada deputado e extrai CNPJs com concentração atípica de pagamentos
3. **Step 3:** Para cada CNPJ suspeito, busca o QSA (sócios) via **BrasilAPI** (`brasilapi.com.br/api/cnpj/v1/{cnpj}`)
4. **Step 4:** Verifica se os CNPJs possuem contratos federais via **Portal da Transparência**
5. **Step 5:** Busca menções em **Diários Oficiais** municipais via **Querido Diário**
6. **Step 6:** Verifica processos judiciais dos sócios via **DataJud**
7. **Step 7:** Monta o grafo completo no Neo4j (nós: Politico, Empresa, Pessoa; arestas: CONTRATOU, SOCIO_ADMINISTRADOR_DE, DOOU_PARA_CAMPANHA)

**Gatherers utilizados internamente:**
```
src/gatherers/transparencia_gatherer.py  → Portal da Transparência (contratos federais)
src/gatherers/brasil_api_gatherer.py     → BrasilAPI (QSA de CNPJs)
src/gatherers/querido_diario_gatherer.py → Querido Diário (diários oficiais)
src/loaders/tse_batch_loader.py          → Doações de campanha (dump TSE)
src/loaders/datajud_loader.py            → Processos judiciais (DataJud)
```

> 🧑‍🔧 **Explicação Simples:** Esse é o "detetive principal". Ele pega um fornecedor suspeito, descobre quem são os donos da empresa, verifica se esses donos doaram para a campanha do deputado, e monta um mapa visual de todas essas conexões. Se o ciclo se fecha (Deputado → Empresa → Sócio → Doador → Deputado), temos um alerta de triangulação.

---

#### Step 13: `EmendasGatherer` (Emendas Parlamentares)
**Script:** `workers/src/gatherers/emendas_gatherer.py`
**O que faz:** Para cada político no banco, busca TODAS as emendas parlamentares de 2022 até hoje no **Portal da Transparência** (via CPF do autor). Para cada emenda encontrada, envia para o backend via `POST /api/internal/workers/ingest/politician/{externalId}/emenda_pix/{municipioIbge}`, que cria:
- O nó `Municipio` (se não existir)
- O relacionamento `(:Politico)-[:ENVIOU_EMENDA {id, ano, valor, tipo}]->(:Municipio)`

#### Step 14: `EmendasPixWorker` (Detecção de Fluxo Circular)
**Script:** `workers/src/gatherers/emendas_pix_worker.py`
**O que faz:** Consulta o Neo4j procurando o **ciclo completo das Emendas Pix**:
```
Deputado -[ENVIOU_EMENDA]-> Prefeitura -[CONTRATOU]-> Empresa -[SOCIO]-> Pessoa -[DOOU]-> Deputado
```
Se encontra, levanta alerta de fluxo circular.

> 🧑‍🔧 **Explicação Simples:** O deputado manda dinheiro público (emenda) para uma prefeitura. A prefeitura contrata uma empresa. O dono dessa empresa doou para a campanha do mesmo deputado. Coincidência? Esse robô rastreia esse ciclo.

#### Step 14.5: `PNCPWorker` (Licitações Municipais)
**Script:** `workers/src/gatherers/pncp_worker.py`
**O que faz:** Para cada município que recebeu emenda (encontrado no Neo4j), busca contratos públicos no **PNCP** (Portal Nacional de Contratações Públicas) e registra no grafo via `POST /api/internal/workers/ingest/municipio/{ibge}/contrato`.

#### Step 16: `CoherenceWorker` (Coerência de Voto)
**Script:** `workers/src/nlp/coherence_worker.py`
**O que faz:** Analisa se os votos do deputado são coerentes com suas promessas. Compara texto dos projetos votados com as promessas registradas usando NLP.

#### Step 17: `GazetteGraphBuilder` (Diários Oficiais → Neo4j)
**Scripts:**
- `workers/src/nlp/gazette_text_fetcher.py` — Busca diários na API do Querido Diário
- `workers/src/nlp/gazette_nlp_extractor.py` — Extrai CNPJs, valores e modalidades de licitação via RegEx e NLP
- `workers/src/nlp/gazette_neo4j_ingester.py` — Ingere os resultados no Neo4j como nós `DiarioOficial` e `Licitacao`

**O que faz:** Busca o termo "dispensa de licitação" nos Diários Oficiais municipais, roda NLP para extrair CNPJs e valores, e cria nós no Neo4j conectando empresas a publicações oficiais.

#### Step 18: `GazetteAggregator` (Consolidação → PostgreSQL)
**Script:** `workers/src/nlp/gazette_aggregator_worker.py`
**O que faz:** Lê os findings do Neo4j (diários oficiais) e consolida em campos do PostgreSQL (`nlpGazetteCount`, `nlpGazetteDetails`).

#### Step 20: `JudicialAggregator` (DataJud → PostgreSQL)
**Script:** `workers/src/gatherers/judicial_aggregator_worker.py`
**O que faz:** Consulta 7 tribunais (TRF1-5, STJ, TST) via **DataJud API** buscando processos de improbidade administrativa associados a cada político. Consolida no PostgreSQL (`judicialRiskScore`, `judicialRiskDetails`).

#### Step 21: `DocumentaryEvidenceWorker` (Trilha de Auditoria)
**Script:** `workers/src/gatherers/documentary_evidence_worker.py`
**O que faz:** Gera relatórios determinísticos (não-ML) para cada político, baixando despesas do ano corrente direto da API da Câmara e salvando um JSON de auditoria em `data/processed/audit_reports/`.

#### Step 23: `RAISWorker` (Detecção de Fantasmas via CLT)
**Script:** `workers/src/gatherers/rais_worker.py`
**O que faz:** Processa dumps da RAIS (Ministério do Trabalho) para encontrar assessores da Câmara que possuem emprego CLT de 40h em outro estado — evidência de "funcionário fantasma".

**⚠️ Requer:** Dumps em `data/raw/rais/` (arquivos CSV da RAIS/PDET).

#### Step 24: `TCUWorker` (Contas Irregulares)
**Script:** `workers/src/gatherers/tcu_worker.py`
**O que faz:** Consulta a API do TCU (Tribunal de Contas da União) buscando contas julgadas irregulares.

**API usada:** `https://dadosabertos.tcu.gov.br/api/rest/v2/contas-irregulares`

#### Step 25: `Database Pruning` (Limpeza)
**O que faz:** Chama `DELETE /api/internal/workers/ingest/prune-empty` no backend. O backend remove políticos "fantasmas" que foram criados por acidente mas não têm nenhum dado útil (sem despesas, sem scores).

#### Step 26: `SuperReportWorker` (Laudo Unificado)
**Script:** `workers/src/gatherers/super_report_worker.py`
**O que faz:** Para cada político que sobreviveu a todo o pipeline, gera um **Super Relatório JSON** unificado que consolida TODOS os dados em um único arquivo de auditoria. Salva em `workers/data/processed/super_reports/`.

**Nome do arquivo gerado:** `super_report_{nome}_{externalId}.json`
**Exemplo real:** `super_report_alberto_fraga_camara_73579.json`

**Estrutura do JSON (4 seções):**

```json
{
    "01_metadados": {
        "internal_id": 412,
        "camara_id": "camara_73579",
        "nome": "Alberto Fraga",
        "partido_estado": "PL - DF",
        "data_extracao": "2026-03-03 14:07:33"
    },
    "02_documentos_lidos_e_grafos": {
        "notas_fiscais_agrupadas": 15,
        "empresas_qsa_e_contratos_mapeados": 3,
        "municipios_recebedores_de_emendas": 2,
        "promessas_campanha_identificadas": 5,
        "votacoes_analisadas_nlp": 12
    },
    "03_estatisticas_patrimoniais_e_uso_maquina": {
        "total_gasto_cota_parlamentar": 430570.17,
        "taxa_ausencia_plenario": 0,
        "patrimonio_declarado_2022": null,
        "fator_anomalia_patrimonial": null
    },
    "04_alertas_de_inteligencia": {
        "motor_rachadinha_score": 10,
        "motor_rachadinha_evidencias": [
            {
                "heuristic": "Doador Compulsório (CEAP Pessoal)",
                "points": 0,
                "max": 40,
                "detail": "Distribuição de gastos com pessoal dentro da normalidade.",
                "source": "Dados abertos da Câmara (CEAP)",
                "proof": "Sem evidências de concentração atípica.",
                "proofData": null
            }
        ],
        "anomalias_contratacao_gabinete_qtd": 3,
        "anomalias_contratacao_gabinete_evidencias": [
            {
                "type": "DESPESA_FISCAL",
                "severity": "MEDIUM",
                "detail": "Documento extraído: BROAD BRASIL LTDA",
                "totalValue": 1050.0,
                "evidence_url": "https://www.camara.leg.br/cota-parlamentar/..."
            }
        ],
        "anomalia_espacial_teletransporte_qtd": null,
        "mencoes_suspeitas_diarios_oficiais": null,
        "processos_judiciais_improbidade": null
    }
}
```

| Seção | O que contém |
|:---|:---|
| `01_metadados` | ID interno, ID da Câmara, nome, partido-estado, data de geração |
| `02_documentos_lidos_e_grafos` | Quantidades de nós processados no Neo4j (despesas, empresas, emendas, promessas, votos) |
| `03_estatisticas_patrimoniais` | Total gasto na CEAP, taxa de ausência, patrimônio declarado, fator de anomalia |
| `04_alertas_de_inteligencia` | Score de rachadinha (0-100) com evidências detalhadas, anomalias de gabinete, teletransporte, diários oficiais, processos judiciais |

> 🧑‍🔧 **Explicação Simples:** No final de tudo, esse robô gera um "dossiê completo" de cada político em formato JSON — um arquivo que contém absolutamente tudo que o sistema descobriu sobre ele. É como o "boletim escolar" do parlamentar: tem as notas em cada matéria (riscos), as provas que fundamentam cada nota, e links para as fontes originais. Qualquer pessoa pode abrir esses arquivos na pasta `workers/data/processed/super_reports/` e auditar os resultados.

---

## 4. O Backend (Spring Boot)

### 4.1 Controllers (Portas de Entrada)

O backend tem **3 controllers** que recebem requisições:

#### `FrontendSearchController` — `/api/v1/politicians/`
Para o **dashboard** (o que o usuário vê):

| Endpoint | Método | O que retorna |
|:---|:---|:---|
| `/search?name=` | GET | Lista de políticos (busca por nome) |
| `/{id}` | GET | Dados detalhados de um político |
| `/{id}/graph` | GET | Dados do grafo (promessas + votos) |
| `/{id}/sources` | GET | Status das fontes de dados |
| `/{id}/expenses` | GET | Lista de despesas (Neo4j → `DespesaNode`) |
| `/{id}/emendas` | GET | Lista de emendas (Neo4j → `ENVIOU_EMENDA`) |

#### `GraphController` — `/api/graph/`
Para os **grafos do Neo4j**:

| Endpoint | Método | O que retorna |
|:---|:---|:---|
| `/network/{externalId}` | GET | Grafo completo (Super Bolhas + Emendas + Follow The Money) |

#### `WorkerIntegrationController` — `/api/internal/workers/ingest/`
Para os **workers Python** (ingestão de dados):

| Endpoint | Método | O que faz |
|:---|:---|:---|
| `/politician` | POST | Cria/atualiza um político |
| `/politician/{id}/promise` | POST | Adiciona uma promessa |
| `/politician/{id}/vote` | POST | Adiciona um voto |
| `/politician/{id}/despesa` | POST | Adiciona uma despesa no Neo4j |
| `/politician/{id}/sessao` | POST | Adiciona uma sessão plenária no Neo4j |
| `/politician/{id}/emenda_pix/{ibge}` | POST | Adiciona uma emenda Pix no Neo4j |
| `/municipio/{ibge}/contrato` | POST | Adiciona um contrato municipal no Neo4j |
| `/pessoa/societario` | POST | Adiciona uma pessoa societária no Neo4j |
| `/deduplicate` | POST | Remove políticos duplicados |
| `/reset-database` | DELETE | Zera o PostgreSQL |
| `/prune-empty` | DELETE | Remove registros fantasma |

### 4.2 DataIngestionService (Lógica de Negócio)

**Arquivo:** `backend/src/main/java/com/tp360/core/service/DataIngestionService.java` (509 linhas)

Este é o serviço que faz a "mágica" de gravar nos dois bancos ao mesmo tempo:
- **`ingestPolitician()`** — Cria ou atualiza um político no PostgreSQL E cria o nó no Neo4j
- **`ingestDespesa()`** — Cria o nó `Despesa` no Neo4j E vincula ao `Politico` com `GEROU_DESPESA`
- **`ingestEmendaPix()`** — Cria o nó `Municipio` (se não existir), o nó `Emenda`, e o relacionamento `ENVIOU_EMENDA`
- **`deduplicatePoliticians()`** — Algoritmo inteligente de merge de duplicados

### 4.3 Queries Cypher (Neo4j)

**Arquivo:** `backend/src/main/java/com/tp360/core/repositories/neo4j/PoliticoNodeRepository.java`

| Query | Usado por | O que faz |
|:---|:---|:---|
| `getFullConnectionGraph()` | GraphController | Monta o grafo "Follow The Money" com Super Bolhas (despesas agrupadas por fornecedor) + emendas + contratos |
| `findTriangulationPath()` | (interno) | Busca o caminho de triangulação de 3º grau no Neo4j |
| `findDespesasByPoliticoId()` | FrontendSearchController | Lista as 15 despesas mais recentes |
| `findEmendasByPoliticoId()` | FrontendSearchController | Lista emendas parlamentares |

**Super Bolhas:** No grafo visual, as despesas são **agrupadas por fornecedor** (não uma bolha por nota fiscal). Isso é feito pela query `getFullConnectionGraph()` que roda `sum(d.valorDocumento)` e `count(d)` por fornecedor, criando "Super Nós" virtuais do tipo `DespesaAgrupada`.

> 🧑‍🔧 **Explicação Simples:** No grafo visual do dashboard, em vez de mostrar 300 bolinhas (uma por nota fiscal), agrupamos por empresa. Se o deputado pagou 65 notas para a TAM totalizando R$83 mil, aparece UMA bolha grande escrito "TAM (65 notas) = R$83.143,78". Quanto maior a bolha, mais dinheiro público foi para aquela empresa.

---

## 5. O Frontend (Dashboard React)

**Arquivo principal:** `frontend/src/App.tsx` (634 linhas)
**Framework:** Vite 7 + React 19 + TypeScript + TailwindCSS

### 5.1 Abas do Dashboard

| Aba | Estado `activeTab` | O que mostra |
|:---|:---|:---|
| **Visão Geral** | `geral` | Evolução patrimonial (gráfico), custos operacionais, últimas despesas |
| **Deep Match** | `inteligencia` | Radar de Risco (RadarRisco), anomalias de pessoal, risco judiciário, menções em diários oficiais |
| **Grafo de Influência** | `grafo` | Grafo interativo "Follow The Money" (ForceGraph2D) |
| **Extrato CEAP** | `despesas` | Tabela com todas as despesas brutas (até 500 registros) |
| **Emendas (Orçamento)** | `emendas` | Tabela com todas as emendas parlamentares |
| **Rastreabilidade** | `fontes` | Status de cada fonte de dados (Câmara, CGU, TSE, DataJud, Querido Diário) |

### 5.2 Componentes Visuais

| Componente | Arquivo | O que faz |
|:---|:---|:---|
| `RadarRisco` | `components/RadarRisco.tsx` | Gráfico radar circular mostrando probabilidade de fraude |
| `PoliticianCard` | `components/Dossie/PoliticianCard.tsx` | Card de perfil do político |
| `WealthChart` | `components/Patrimonio/WealthChart.tsx` | Gráfico de barras da evolução patrimonial (Recharts) |
| `ConfidenceBadge` | `components/Rastreabilidade/ConfidenceBadge.tsx` | Badge de nível de confiança dos dados |

### 5.3 Fluxo de Dados no Frontend

Quando o usuário seleciona um político, a função `selectPolitician()` faz **5 chamadas simultâneas**:

```
1. GET /api/graph/network/{externalId}     → Grafo Neo4j (Follow The Money)
2. GET /api/v1/politicians/{id}/expenses   → Despesas brutas (tabela CEAP)
3. GET /api/v1/politicians/{id}/emendas    → Emendas parlamentares
4. GET /api/v1/politicians/{id}/sources    → Status das fontes
5. GET /api/v1/politicians/{id}/expenses   → Detalhamento das últimas despesas
```

> 🧑‍🔧 **Explicação Simples:** Quando você clica no nome de um deputado, o dashboard busca TODOS os dados dele de uma vez — o grafo, as despesas, as emendas, tudo. É por isso que o dashboard carrega tão rápido.

---

## 6. Fontes de Dados Reais Utilizadas

| Fonte | Tipo | Requer API Key? | Workers que a consomem |
|:---|:---|:---|:---|
| **Câmara dos Deputados** | REST API | ❌ | CamaraGatherer, ExpensesWorker, AbsencesWorker, RachadinhaWorker, StaffAnomalyWorker, CrossMatch, CamaraNLP |
| **Portal da Transparência (CGU)** | REST API | ✅ `PORTAL_API_KEY` | EmendasGatherer, TransparenciaGatherer, CrossMatch |
| **TSE (Dados Eleitorais)** | Dumps CSV | ❌ | TSE ETL, WealthAnomalyWorker, TSEBatchLoader |
| **Receita Federal (QSA)** | Dumps CSV | ❌ | Receita Federal ETL |
| **BrasilAPI** | REST API | ❌ | CrossMatchOrchestrator (Step 3), RachadinhaWorker (H3) |
| **Querido Diário (OKBR)** | REST API | ❌ | GazetteTextFetcher, CrossMatch (Step 5), RachadinhaWorker (H4) |
| **DataJud (CNJ)** | REST API | ❌ | JudicialAggregator, CrossMatch (Step 6), RachadinhaWorker (H5) |
| **PNCP** | REST API | ❌ | PNCPWorker |
| **TCU** | REST API | ❌ | TCUWorker |
| **RAIS/PDET** | Dumps CSV | ❌ | RAISWorker |

---

## 7. Módulo NLP (Processamento de Linguagem Natural)

O projeto tem um módulo NLP dedicado em `workers/src/nlp/`:

| Arquivo | O que faz |
|:---|:---|
| `gazette_text_fetcher.py` | Busca e baixa textos de Diários Oficiais da API do Querido Diário |
| `gazette_nlp_extractor.py` | Extrai entidades dos textos: CNPJs (RegEx), valores monetários, modalidades de licitação, score de suspeição |
| `gazette_neo4j_ingester.py` | Ingere os resultados no Neo4j como nós `DiarioOficial` e relacionamentos |
| `gazette_aggregator_worker.py` | Consolida findings do Neo4j → campos do PostgreSQL |
| `coherence_worker.py` | Compara promessas vs votos usando similaridade textual |
| `regex_patterns.py` | Padrões RegEx para extração de CNPJs e valores monetários |
| `spacy_ner.py` | NER (Named Entity Recognition) com spaCy |

> 🧑‍🔧 **Explicação Simples:** Os robôs de NLP leem documentos oficiais do governo (como o Diário Oficial) e destacam automaticamente os trechos importantes — como "Dispensa de Licitação no valor de R$50.000 para o CNPJ 12.345.678/0001-90". Em vez de um ser humano ler milhares de páginas, o robô faz isso em segundos.

---

## 8. Mapa de Diretórios de Dados

```
data/
├── raw/                          # Dados brutos baixados
│   ├── camara/                   # Parquets da Câmara (CEAP, presenças)
│   ├── cgu/                      # Parquets do Portal da Transparência
│   ├── tse/                      # CSVs do TSE (doações, bens)
│   ├── receita/                  # CSVs da Receita Federal (QSA)
│   ├── rais/                     # Dumps da RAIS (*opcional)
│   └── diarios/                  # Textos de Diários Oficiais
│
├── clean/                        # Dados limpos (pós-ETL)
│   ├── tse/                      # Parquets processados 
│   └── receita/                  # Parquets processados
│
├── downloads/                    # Arquivos temporários
│   ├── diarios_oficiais/         # PDFs e textos
│   └── notas_fiscais/            # PDFs de notas fiscais
│
└── processed/                    # Saídas finais dos workers
    ├── rachadinha_reports/        # JSONs do RachadinhaWorker
    ├── staff_anomalies/          # JSONs do StaffAnomalyWorker
    ├── audit_reports/            # JSONs do DocumentaryEvidenceWorker
    ├── super_reports/            # JSONs do SuperReportWorker
    └── pipeline_summary.json     # Relatório final do pipeline
```

---

## 9. API de Integração (Workers ↔ Backend)

Todos os workers Python se comunicam com o backend Java via chamadas HTTP REST. O módulo `workers/src/core/api_client.py` fornece 3 clientes:

| Classe | Base URL | Uso |
|:---|:---|:---|
| `BackendClient` | `http://localhost:8080` | Envia dados para o backend (ingestão) |
| `GovAPIClient` | (configurável) | Consome APIs governamentais com rate limiting |
| `PortalTransparenciaClient` | `https://api.portaldatransparencia.gov.br` | CGU com API key automática |

> 🧑‍🔧 **Explicação Simples:** Os robôs Python não falam diretamente com o banco de dados. Eles enviam os dados para o backend Java via "requisições HTTP", como se fossem preenchendo formulários na internet. O backend recebe e guarda nos bancos.

---

## 10. Como Contribuir (Pontos de Extensão)

Se você quer adicionar um novo detector de fraude ao sistema:

1. **Crie um novo worker** em `workers/src/gatherers/meu_novo_worker.py`
2. **Registre no pipeline** adicionando um novo `run_step(N, "Nome", step_N)` em `run_all_extractions.py`
3. **Se precisar gravar no PostgreSQL:** Adicione um campo na entidade `Politician.java` e use o `BackendClient` para enviar via PUT
4. **Se precisar gravar no Neo4j:** Use o `WorkerIntegrationController` para enviar nós e relacionamentos

Se você quer melhorar o frontend:
1. **Novos componentes** vão em `frontend/src/components/`
2. **Novas abas** precisam: adicionar o valor no tipo do `activeTab`, criar o botão, e adicionar o bloco `{activeTab === 'minha_aba' && (...)}` no JSX

---

**⚠️ Aviso Legal:** Este sistema utiliza **exclusivamente** APIs Públicas e Dados Abertos protegidos pela **Lei de Acesso à Informação (LAI)**. Nenhum dado privado ou sigiloso é coletado ou armazenado.
