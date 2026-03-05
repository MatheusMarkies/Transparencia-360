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
│   │  Vite+React   │◄──►│  Spring Boot     │◄──►│  Pipeline de Extração    │ │
│   │  :5173        │    │  :8080           │    │                          │ │
│   │               │    │                  │    │  • Coleta de dados       │ │
│   │  O que o      │    │  O "cérebro"     │    │  • Rosie Engine (14 clf) │ │
│   │  usuário vê   │    │  que organiza    │    │  • Análises de risco     │ │
│   │  (dashboard)  │    │  tudo            │    │  • Construção de grafos  │ │
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
- **Contagens da Rosie** — Anomalias detectadas por tipo de classificador (Benford, Duplicatas, Fim de Semana, Saúde, Luxo)
- Anomalias de teletransporte, emendas Pix, funcionários fantasma

**Entidade Principal — `Politician` (39 campos):**

| Campo | Tipo | Fonte |
|:---|:---|:---|
| `name`, `party`, `state`, `position` | String | CamaraGatherer |
| `absences`, `presences` | Integer | AbsencesWorker |
| `expenses` | Double | ExpensesWorker |
| `stateAffinity` | Double | StateAffinityWorker |
| `propositions`, `frentes` | Integer | CamaraGatherer |
| `declaredAssets` (2014, 2018, 2022) | Double | TSE ETL |
| `wealthAnomaly` | Double | WealthAnomalyWorker |
| `staffAnomalyCount` + Details | Integer/TEXT | StaffAnomalyWorker |
| `cabinetRiskScore` + Details | Integer/TEXT | RachadinhaWorker |
| `ghostEmployeeCount` + Details | Integer/TEXT | GhostEmployeeWorker |
| `nlpGazetteCount` + Score + Details | Integer/TEXT | GazetteAggregator |
| `judicialRiskScore` + Details | Integer/TEXT | JudicialAggregator |
| `cabinetSize` + Details | Integer/TEXT | CamaraCabinetScraper |
| `rosieBenfordCount` | Integer | RosieWorker |
| `rosieDuplicateCount` | Integer | RosieWorker |
| `rosieWeekendCount` | Integer | RosieWorker |
| `rosieHealthCount` | Integer | RosieWorker |
| `rosieLuxuryCount` | Integer | RosieWorker |
| `teleportAnomalyCount` + Details | Integer/TEXT | SpatialAnomalyWorker |
| `emendasPixAnomalyCount` + Details | Integer/TEXT | EmendasPixWorker |
| `overallRiskScore` *(calculado)* | Double | Fórmula: 75% Rachadinha + 25% Faltas |

**Outras Entidades:**
| Classe Java | Tabela | O que guarda |
|:---|:---|:---|
| `Politician` | `politicians` | Dados consolidados do parlamentar |
| `Promise` | `promises` | Promessas extraídas de discursos |
| `Vote` | `votes` | Votos nominais no plenário |

**Arquivo de configuração:** `backend/src/main/resources/application.yml`
```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5433/tp360
    username: postgres
    password: password
```

> 🧑‍🔧 **Explicação Simples:** O PostgreSQL é como uma planilha Excel gigante onde guardamos os dados de cada político em linhas e colunas. "Quanto ele gastou?", "Qual o patrimônio dele?", "Quantas anomalias a Rosie encontrou?" — tudo fica aqui.

### 2.2 Neo4j (Banco de Grafos) — `:7687` (dados) / `:7474` (interface web)

Armazena as **conexões entre entidades** — quem pagou quem, quem é sócio de quem, para qual prefeitura foi a emenda.

**Nós (Nodes) implementados:**
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

**Relacionamentos implementados:**
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

O arquivo `workers/run_all_extractions.py` é o **orquestrador principal** (v3.1). Ele executa etapas divididas em **3 fases**.

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

> 🧑‍🔧 **Explicação Simples:** Esse é o "botão vermelho" do sistema. Quando você roda esse script, ele dispara uma série de robôs que vão buscar dados em sites do governo, calcular riscos, montar grafos e gerar laudos. O `--limit` controla quantos políticos processar (comece com 1 para testar). O `--keep-db` pula as fases de download pesado e só roda as análises.

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

#### Step 1: `CamaraGatherer` (Base Data)
**Script:** `workers/src/gatherers/camara_gatherer.py`
**O que faz:** Busca a lista de deputados na API da Câmara e envia cada um para o backend via `POST /api/internal/workers/ingest/politician`.

> 🧑‍🔧 **Explicação Simples:** É o primeiro passo — descobre quem são os deputados em exercício e salva os dados de base (nome, partido, estado, foto).

#### Step 2: `Camara Extractors` (Presenças)
**Script:** `extractors/camara_deputados.py`
**O que faz:** Baixa registros de presença no plenário usando HTTP assíncrono (httpx).

**API usada:** `https://dadosabertos.camara.leg.br/api/v2`
- `GET /eventos?dataInicio=YYYY-MM-DD` → Presenças

> 🧑‍🔧 **Explicação Simples:** Baixa o registro de quando os deputados estiveram (ou não) no plenário.

#### Steps Opcionais (comentados no pipeline):
| Step | Worker | Status | Motivo |
|:---|:---|:---|:---|
| 7 | `TSE ETL` | 💤 Comentado | Requer dumps CSV massivos (~30GB). Descomente quando os arquivos estiverem em `data/raw/tse/` |
| 22 | `Receita Federal ETL` | 💤 Comentado | Requer dumps QSA da Receita Federal em `data/raw/receita/` |

---

### FASE 2 — Ingestão e Limpeza

> Só executa se `--keep-db` NÃO foi passado.

#### Step 4: `ExpensesWorker` (Legacy Sync)
**Script:** `workers/src/gatherers/expenses_worker.py`
**O que faz:** Busca despesas da Câmara API (anos 2023-2026) e envia para o backend via `POST /api/internal/workers/ingest/politician/{externalId}/despesa` — gravando tanto no PostgreSQL (total acumulado) quanto no Neo4j (cada nota individual como nó `Despesa`).

#### Step 5: `AbsencesWorker`
**Script:** `workers/src/gatherers/absences_worker.py`
**O que faz:** Busca presenças e ausências no plenário (anos 2023-2026), ingerindo sessões no Neo4j via `POST /api/internal/workers/ingest/politician/{externalId}/sessao`. Possui **cache local** com estrutura `{"resumo": {...}, "detalhes": [...]}` para evitar re-downloads.

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

#### Step 10: `RachadinhaScoringWorker v2.0` (Motor de Risk Score)
**Script:** `workers/src/gatherers/rachadinha_worker.py` (31.683 bytes — **o maior arquivo do projeto**)

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

#### Step 15: `ROSIE — Full CEAP Anomaly Detection Engine`
**Scripts:** `workers/src/gatherers/rosie_worker.py` + `workers/src/gatherers/rosie_engine.py` (58.267 bytes)

Motor de detecção de anomalias inspirado na [Operação Serenata de Amor](https://serenata.ai), baseado no projeto original [okfn-brasil/serenata-de-amor/rosie](https://github.com/okfn-brasil/serenata-de-amor/tree/main/rosie). Roda **14 classificadores** sobre todas as notas fiscais da CEAP (anos 2023-2026):

| # | Classificador | O que detecta | Método |
|:---|:---|:---|:---|
| 1 | `MealPriceOutlier` | Refeições com valor fora do padrão | IQR (Intervalo Interquartil) por categoria |
| 2 | `TravelSpeed` | Viagens fisicamente impossíveis | Haversine (velocidade entre despesas) |
| 3 | `MonthlySubquotaLimit` | Subcota mensal estourada | Limites reais por UF/subcota |
| 4 | `ElectionPeriod` | Gastos durante campanha eleitoral | Calendário eleitoral TSE |
| 5 | `WeekendHoliday` | Despesas em fins de semana e feriados | Calendário + categoria |
| 6 | `DuplicateReceipt` | Recibos duplicados (mesma nota 2x) | Hash MD5 (fornecedor+valor+data) |
| 7 | `CNPJBlacklist` | Empresas no CEIS/CNEP (inidôneas) | Cruzamento com blacklist |
| 8 | `CompanyAge` | Pagamentos a empresas muito novas | Data fundação via Receita Federal |
| 9 | `BenfordLaw` | Distribuição de dígitos manipulada | Chi² (Lei de Benford) |
| 10 | `HighValueOutlier` | Valor fora da curva (z-score global) | Z-score por categoria |
| 11 | `SuspiciousSupplier` | Fornecedor que atende muitos deputados | Limiar de 30 deputados |
| 12 | `SequentialReceipt` | Notas fiscais com numeração sequencial | Detecção de runs consecutivos |
| 13 | `PersonalHealthExpense` | Gastos médicos/estéticos proibidos na CEAP | RegEx em nomes de fornecedores |
| 14 | `LuxuryPersonalExpense` | Pet shops, joalherias, resorts | RegEx em nomes de fornecedores |

**Pipeline interno:**
1. **Fit** — Cada classificador é treinado no dataset completo (calcula estatísticas, limites, fingerprints)
2. **Predict** — Cada recibo é avaliado por todos os 14 classificadores
3. **Risk Score** — Score de 0 a 100 por deputado (combina volume, severidade e amplitude)
4. **Push** — Envia contagens para o backend via `POST /api/internal/workers/ingest/politician`
5. **Punishment** — Lê o CSV de anomalias e injeta penalidades no `cabinetRiskScore` existente

**Saídas geradas:**
- `data/processed/rosie_report.json` — Relatório estruturado completo
- `data/processed/rosie_anomalies.csv` — Lista flat de anomalias
- `data/processed/rosie_risk_ranking.txt` — Ranking legível por humanos
- `data/processed/rosie_reports/` — Relatório individual por deputado (JSON)
- Campos no PostgreSQL: `rosieBenfordCount`, `rosieDuplicateCount`, `rosieWeekendCount`, `rosieHealthCount`, `rosieLuxuryCount`

> 🧑‍🔧 **Explicação Simples:** A Rosie é como uma auditora fiscal automática. Ela lê TODAS as notas fiscais de cada deputado e aplica 14 testes matemáticos diferentes. Se a nota fiscal de refeição custa R$800 (outlier), se o deputado teve gastos em joalherias (proibido), se a distribuição de valores viola a Lei de Benford (possível manipulação) — tudo isso é flagado automaticamente. O resultado é um "raio-X completo" dos gastos de cada parlamentar.

---

#### Steps 17-18: `GazetteGraphBuilder` + `GazetteAggregator`
**Scripts:** `workers/src/nlp/gazette_text_fetcher.py` + `gazette_neo4j_ingester.py` + `gazette_aggregator_worker.py`

**O que fazem (em sequência):**
1. Busca "dispensa de licitação" nos Diários Oficiais municipais via **Querido Diário API**
2. Extrai CNPJs, valores e modalidades via RegEx + NLP
3. Ingere no Neo4j como nós `DiarioOficial` e `Licitacao`
4. Consolida findings no PostgreSQL (`nlpGazetteCount`, `nlpGazetteScore`, `nlpGazetteDetails`)

#### Step 20: `JudicialAggregator`
**Script:** `workers/src/gatherers/judicial_aggregator_worker.py`
**O que faz:** Consulta 7 tribunais (TRF1-5, STJ, TST) via **DataJud API** buscando processos de improbidade administrativa associados a cada político. Consolida no PostgreSQL (`judicialRiskScore`, `judicialRiskDetails`).

#### Step 21: `DocumentaryEvidenceWorker`
**Script:** `workers/src/gatherers/documentary_evidence_worker.py`
**O que faz:** Gera relatórios determinísticos (não-ML) para cada político, baixando despesas do ano corrente direto da API da Câmara e salvando um JSON de auditoria em `data/processed/audit_reports/`.

#### Step 23: `RAISWorker` (Detecção de Fantasmas via CLT)
**Script:** `workers/src/gatherers/rais_worker.py`
**O que faz:** Processa dumps da RAIS (Ministério do Trabalho) para encontrar assessores da Câmara que possuem emprego CLT de 40h em outro estado — evidência de "funcionário fantasma".

**⚠️ Requer:** Dumps em `data/raw/rais/` (arquivos CSV da RAIS/PDET).

#### Step 24: `TCUWorker`
**Script:** `workers/src/gatherers/tcu_worker.py`
**O que faz:** Consulta a API do TCU (Tribunal de Contas da União) buscando contas julgadas irregulares.

**API usada:** `https://dadosabertos.tcu.gov.br/api/rest/v2/contas-irregulares`

#### Step 25: `Database Pruning`
**O que faz:** Chama `DELETE /api/internal/workers/ingest/prune-empty` no backend. O backend remove políticos "fantasmas" que foram criados por acidente mas não têm nenhum dado útil (sem despesas, sem scores).

#### Step 26: `SuperReportWorker` (Laudo Unificado)
**Script:** `workers/src/gatherers/super_report_worker.py`
**O que faz:** Para cada político que sobreviveu a todo o pipeline, gera um **Super Relatório JSON** unificado que consolida TODOS os dados em um único arquivo de auditoria. Salva em `data/processed/super_reports/`.

**Nome do arquivo gerado:** `super_report_{nome}_{id}.json`
**Exemplo real:** `super_report_acácio_favacho_204379.json`

**Estrutura do JSON (3 seções):**

```json
{
    "metadata": {
        "gerado_em": "2026-03-05T00:49:04",
        "deputado_id": "204379",
        "nome": "Acácio Favacho"
    },
    "evidencias_rosie": {
        "deputado_nome": "Acácio Favacho",
        "risco_score": 100.0,
        "total_anomalias": 1383,
        "classificadores_acionados": 6,
        "principais_anomalias": [
            {
                "classifier": "HighValueOutlierClassifier",
                "confidence": 0.95,
                "reason": "Valor R$ 98,350.00 é outlier para 'DIVULGAÇÃO'..."
            }
        ],
        "todas_anomalias_detalhadas": ["... (lista completa)"]
    },
    "resumo": {
        "total_gasto_cota": 856231.17,
        "ausencias": 15,
        "presencas": 204,
        "patrimonio_2022": null,
        "anomalias_gabinete": 3,
        "score_rachadinha": 10,
        "teletransporte": null,
        "diarios_oficiais": null,
        "processos_judiciais": null
    }
}
```

> 🧑‍🔧 **Explicação Simples:** No final de tudo, esse robô gera um "dossiê completo" de cada político em formato JSON — um arquivo que contém absolutamente tudo que o sistema descobriu sobre ele, incluindo TODAS as anomalias da Rosie com os detalhes de cada infração. É como o "boletim escolar" do parlamentar.

---

#### Steps Opcionais (comentados no pipeline):
| Step | Worker | Status | Motivo |
|:---|:---|:---|:---|
| 8 | `WealthAnomalyWorker` | 💤 Comentado | Requer dados do TSE pré-carregados |
| 9 | `StaffAnomalyWorker` | 💤 Comentado | Depende de dados completos de despesas |
| 11 | `SpatialAnomalyWorker` | 💤 Comentado | Depende de dados de presenças no Neo4j |
| 13 | `EmendasGatherer` | 💤 Comentado | Requer Portal da Transparência (lento) |
| 14 | `EmendasPixWorker` | 💤 Comentado | Depende de Step 13 |
| 14.5 | `PNCPWorker` | 💤 Comentado | Depende do grafo de emendas |
| 15 (antigo) | `CamaraNLPGatherer` | 💤 Comentado | Download pesado de discursos |
| 16 | `CoherenceWorker` | 💤 Comentado | Análise NLP de promessas vs votos |

> [!NOTE]
> Esses workers estão funcionais mas desabilitados no pipeline principal para economizar tempo de execução. Para ativá-los, descomente as linhas correspondentes em `run_all_extractions.py`.

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
| `/external/{externalId}` | GET | Busca por externalId (ex: `camara_204379`) |
| `/{id}/graph` | GET | Dados do grafo (promessas + votos) |
| `/{id}/sources` | GET | Status das fontes de dados |
| `/{id}/expenses` | GET | Lista de despesas (Neo4j → `DespesaNode`) |
| `/{id}/emendas` | GET | Lista de emendas (Neo4j → `ENVIOU_EMENDA`) |
| `/{id}/top-fornecedores` | GET | Top fornecedores por valor gasto |
| `/{id}/gastos-categoria` | GET | Gastos agrupados por categoria |
| *(POST)* | POST | Atualiza/cria um político (usado pela Rosie punishment) |

#### `GraphController` — `/api/graph/`
Para os **grafos do Neo4j**:

| Endpoint | Método | O que retorna |
|:---|:---|:---|
| `/triangulation/{politicoId}` | GET | Caminhos de triangulação de 3° grau |
| `/network/{politicoId}` | GET | Grafo completo (Super Bolhas + Emendas + Follow The Money) |

#### `WorkerIntegrationController` — `/api/internal/workers/ingest/`
Para os **workers Python** (ingestão de dados):

| Endpoint | Método | O que faz |
|:---|:---|:---|
| `/politician` | POST | Cria/atualiza um político (upsert por `externalId` ou `name`) |
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

**Arquivo:** `backend/src/main/java/com/tp360/core/service/DataIngestionService.java`

Este é o serviço que faz a "mágica" de gravar nos dois bancos ao mesmo tempo:
- **`ingestPolitician()`** — Cria ou atualiza um político no PostgreSQL E cria o nó no Neo4j. Usa **upsert inteligente**: campos não-nulos do payload atualizam o registro existente, campos nulos são ignorados.
- **`ingestDespesa()`** — Cria o nó `Despesa` no Neo4j E vincula ao `Politico` com `GEROU_DESPESA`
- **`ingestEmendaPix()`** — Cria o nó `Municipio` (se não existir), o nó `Emenda`, e o relacionamento `ENVIOU_EMENDA`
- **`deduplicatePoliticians()`** — Algoritmo inteligente de merge de duplicados

### 4.3 Queries Cypher (Neo4j)

**Arquivo:** `backend/src/main/java/com/tp360/core/repositories/neo4j/PoliticoNodeRepository.java`

| Query | Usado por | O que faz |
|:---|:---|:---|
| `getFullConnectionGraph()` | GraphController | Monta o grafo "Follow The Money" com Super Bolhas (despesas agrupadas por fornecedor) + emendas + contratos |
| `findTriangulationPath()` | GraphController | Busca o caminho de triangulação de 3° grau no Neo4j |
| `findDespesasByPoliticoId()` | FrontendSearchController | Lista as 15 despesas mais recentes |
| `findEmendasByPoliticoId()` | FrontendSearchController | Lista emendas parlamentares |

**Super Bolhas:** No grafo visual, as despesas são **agrupadas por fornecedor** (não uma bolha por nota fiscal). Isso é feito pela query `getFullConnectionGraph()` que roda `sum(d.valorDocumento)` e `count(d)` por fornecedor, criando "Super Nós" virtuais do tipo `DespesaAgrupada`.

> 🧑‍🔧 **Explicação Simples:** No grafo visual do dashboard, em vez de mostrar 300 bolinhas (uma por nota fiscal), agrupamos por empresa. Se o deputado pagou 65 notas para a TAM totalizando R$83 mil, aparece UMA bolha grande escrito "TAM (65 notas) = R$83.143,78". Quanto maior a bolha, mais dinheiro público foi para aquela empresa.

---

## 5. O Frontend (Dashboard React)

**Arquivo principal:** `frontend/src/App.tsx`
**Framework:** Vite 7 + React 19 + TypeScript + TailwindCSS

### 5.1 Abas do Dashboard

| Aba | Estado `activeTab` | O que mostra |
|:---|:---|:---|
| **Visão Geral** | `geral` | Evolução patrimonial (gráfico), custos operacionais, últimas despesas |
| **Deep Match** | `inteligencia` | Radar de Risco (RadarRisco), anomalias de pessoal, risco judiciário, menções em diários oficiais, **contagens da Rosie** (Benford, Duplicatas, Fim de Semana, Saúde, Luxo) |
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

### 5.3 Interface `Politician` (TypeScript)

A interface que define os dados que o frontend espera receber do backend:

```typescript
interface Politician {
  id: number;
  externalId: string;
  name: string;
  party: string;
  state: string;
  position: string;
  absences: number;
  presences: number;
  expenses: number;
  stateAffinity: number;
  propositions: number;
  frentes: number;
  declaredAssets: number;
  declaredAssets2018: number;
  declaredAssets2014: number;
  wealthAnomaly: number;
  staffAnomalyCount: number;
  staffAnomalyDetails: string;       // JSON
  cabinetRiskScore: number;
  cabinetRiskDetails: string;         // JSON
  ghostEmployeeCount: number;
  ghostEmployeeDetails: string;       // JSON
  nlpGazetteCount: number;
  nlpGazetteScore: number;
  nlpGazetteDetails: string;          // JSON
  judicialRiskScore: number;
  judicialRiskDetails: string;         // JSON
  cabinetSize: number;
  cabinetDetails: string;              // JSON
  rosieBenfordCount: number;           // ← Rosie
  rosieDuplicateCount: number;         // ← Rosie
  rosieWeekendCount: number;           // ← Rosie
  rosieHealthCount: number;            // ← Rosie
  rosieLuxuryCount: number;            // ← Rosie
  teleportAnomalyCount: number;
  teleportAnomalyDetails: string;      // JSON
  emendasPixAnomalyCount: number;
  emendasPixAnomalyDetails: string;    // JSON
  overallRiskScore: number;            // Calculado pelo backend
}
```

### 5.4 Fluxo de Dados no Frontend

Quando o usuário seleciona um político, a função `selectPolitician()` faz **5 chamadas simultâneas**:

```
1. GET /api/graph/network/{externalId}     → Grafo Neo4j (Follow The Money)
2. GET /api/v1/politicians/{id}/expenses   → Despesas brutas (tabela CEAP)
3. GET /api/v1/politicians/{id}/emendas    → Emendas parlamentares
4. GET /api/v1/politicians/{id}/sources    → Status das fontes
5. GET /api/v1/politicians/{id}            → Detalhamento completo (todos os campos)
```

> 🧑‍🔧 **Explicação Simples:** Quando você clica no nome de um deputado, o dashboard busca TODOS os dados dele de uma vez — o grafo, as despesas, as emendas, tudo. É por isso que o dashboard carrega tão rápido.

---

## 6. A Rosie Engine em Detalhe

**Arquivo:** `workers/src/gatherers/rosie_engine.py` (1.369 linhas, 58KB)
**Origem:** [okfn-brasil/serenata-de-amor/rosie](https://github.com/okfn-brasil/serenata-de-amor/tree/main/rosie) (Operação Serenata de Amor)

A Rosie Engine é o **maior módulo individual** do projeto. Ela opera em um pipeline de 4 fases:

```
 Recibos CEAP ──► [FIT] Treina 14 classificadores
                   │
                   ▼
              [PREDICT] Avalia cada recibo
                   │
                   ▼
              [RISK SCORE] Pontuação 0-100 por deputado
                   │
                   ▼
              [REPORT] JSON + CSV + Ranking
```

### 6.1 Hierarquia de Classes

```
BaseClassifier (ABC)
├── MealPriceOutlierClassifier   — IQR por categoria de despesa
├── TravelSpeedClassifier         — Haversine entre despesas consecutivas
├── MonthlySubquotaLimitClassifier — Limites mensais por subcota/UF
├── ElectionPeriodClassifier      — Calendário eleitoral TSE
├── WeekendHolidayClassifier      — Fins de semana + feriados nacionais
├── DuplicateReceiptClassifier    — Hash fingerprint (MD5)
├── CNPJBlacklistClassifier       — CEIS/CNEP
├── CompanyAgeClassifier          — Idade da empresa vs data da despesa
├── BenfordLawClassifier          — Chi² sobre distribuição de primeiro dígito
├── HighValueOutlierClassifier    — Z-score global por categoria
├── SuspiciousSupplierClassifier  — Fornecedor servindo > 30 deputados
├── SequentialReceiptClassifier   — Numeração sequencial de notas
├── PersonalHealthExpenseClassifier — RegEx: clínicas, odonto, farmácia
└── LuxuryPersonalExpenseClassifier — RegEx: pet shop, joalheria, resort
```

### 6.2 Fórmula de Risk Score

```python
risk_score = (
    total_confidence * 0.4 +           # Soma das confianças de todas as anomalias
    n_classifiers_triggered * 10 * 0.3 + # Amplitude (quantos classificadores diferentes)
    min(n_anomalies, 50) * 0.3          # Volume (até 50 anomalias)
)
risk_score = min(risk_score, 100.0)    # Normalizado para 0-100
```

### 6.3 Fluxo de Dados: Rosie → Backend → Frontend

```
rosie_engine.py                    rosie_worker.py                 Backend (Java)              Frontend (React)
┌──────────────┐    analyze()     ┌──────────────────┐  POST      ┌─────────────────┐  GET    ┌──────────────────┐
│ 14 classifiers├───────────────►│ classifier_counts ├──────────►│ Politician       ├────────►│ Politician       │
│ fit() + predict()              │ por deputado      │ /ingest/  │ .rosieBenfordCount│ /api/ │ .rosieBenfordCount│
│                                │                   │ politician│ .rosieDuplicateCount      │ .rosieDuplicateCount
│ report["deputy_risk_scores"]   │ counts = scores   │           │ .rosieWeekendCount│       │ .rosieWeekendCount│
│   └─ "classifier_counts"      │   .get("classifier_counts")  │ .rosieHealthCount │       │ .rosieHealthCount │
│      └─ {"BenfordLaw": 42}    │                   │           │ .rosieLuxuryCount │       │ .rosieLuxuryCount │
└──────────────┘                 └──────────────────┘           └─────────────────┘         └──────────────────┘
```

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

## 8. Fontes de Dados Reais Utilizadas

| Fonte | Tipo | Requer API Key? | Workers que a consomem |
|:---|:---|:---|:---|
| **Câmara dos Deputados** | REST API | ❌ | CamaraGatherer, ExpensesWorker, AbsencesWorker, RachadinhaWorker, StaffAnomalyWorker, CrossMatch, CamaraNLP, **RosieWorker** |
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

## 9. Mapa de Diretórios de Dados

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
│   ├── notas_fiscais/            # PDFs de notas fiscais
│   └── camara_docs/              # Documentos baixados
│
└── processed/                    # Saídas finais dos workers
    ├── rachadinha_reports/        # JSONs do RachadinhaWorker
    ├── staff_anomalies/          # JSONs do StaffAnomalyWorker
    ├── audit_reports/            # JSONs do DocumentaryEvidenceWorker
    ├── rosie_reports/            # JSONs individuais da Rosie por deputado
    ├── super_reports/            # JSONs do SuperReportWorker (dossiê completo)
    ├── rosie_report.json         # Relatório geral da Rosie
    ├── rosie_anomalies.csv       # Lista flat de anomalias
    ├── rosie_risk_ranking.txt    # Ranking legível
    └── pipeline_summary.json     # Relatório final do pipeline
```

---

## 10. Workers Auxiliares (Gatherers Internos)

Além dos workers que rodam como steps do pipeline, existem módulos auxiliares:

| Worker | Arquivo | O que faz |
|:---|:---|:---|
| `BrasilAPIGatherer` | `brasil_api_gatherer.py` | Consulta QSA de CNPJs na BrasilAPI |
| `TransparenciaGatherer` | `transparencia_gatherer.py` | Contratos federais no Portal da Transparência |
| `TransparenciaWorker` | `transparencia_worker.py` | Worker de extração do Portal |
| `QueridoDiarioGatherer` | `querido_diario_gatherer.py` | Busca em Diários Oficiais municipais |
| `CamaraCabinetScraper` | `camara_cabinet_scraper.py` | Raspa lista de funcionários do gabinete |
| `CamaraNLPGatherer` | `camara_nlp_gatherer.py` | Baixa discursos parlamentares |
| `SenadoGatherer` | `senado_gatherer.py` | Extrai dados do Senado Federal |
| `TSEWorker` | `tse_worker.py` | Match de patrimônio TSE ↔ Deputados |
| `StateAffinityWorker` | `state_affinity_worker.py` | Calcula afinidade estadual dos gastos |
| `GhostEmployeeWorker` | `ghost_employee_worker.py` | Detecção de funcionários fantasma |
| `SpatialAnomalyWorker` | `spatial_anomaly_worker.py` | Detecção de teletransporte |
| `EmendasPixWorker` | `emendas_pix_worker.py` | Detecção de fluxo circular |

---

## 11. API de Integração (Workers ↔ Backend)

Todos os workers Python se comunicam com o backend Java via chamadas HTTP REST. O módulo `workers/src/core/api_client.py` fornece 3 clientes:

| Classe | Base URL | Uso |
|:---|:---|:---|
| `BackendClient` | `http://localhost:8080` | Envia dados para o backend (ingestão) |
| `GovAPIClient` | (configurável) | Consome APIs governamentais com rate limiting |
| `PortalTransparenciaClient` | `https://api.portaldatransparencia.gov.br` | CGU com API key automática |

> 🧑‍🔧 **Explicação Simples:** Os robôs Python não falam diretamente com o banco de dados. Eles enviam os dados para o backend Java via "requisições HTTP", como se fossem preenchendo formulários na internet. O backend recebe e guarda nos bancos.

---

## 12. Infraestrutura (Docker Compose)

O `docker-compose.yml` define 3 serviços:

| Serviço | Imagem | Container | Porta | Volume Local |
|:---|:---|:---|:---|:---|
| **PostgreSQL 15** | `postgres:15-alpine` | `tp360-db` | `5433` | `./db_data/postgres/` |
| **Neo4j 5.26** | `neo4j:5.26.0` | `tp360-neo4j` | `7474` / `7687` | `./db_data/neo4j/` |
| **Backend** | Build local | `tp360-backend` | `8080` | — |

Ambos os bancos têm **healthchecks** configurados e os dados são persistidos em pastas locais (`db_data/`), não em volumes Docker anônimos.

---

## 13. Como Contribuir (Pontos de Extensão)

Se você quer adicionar um novo detector de fraude ao sistema:

1. **Crie um novo worker** em `workers/src/gatherers/meu_novo_worker.py`
2. **Registre no pipeline** adicionando um novo `run_step(N, "Nome", step_N)` em `run_all_extractions.py`
3. **Se precisar gravar no PostgreSQL:** Adicione um campo na entidade `Politician.java`, adicione getter/setter, e use o endpoint `POST /api/internal/workers/ingest/politician` para enviar via upsert
4. **Se precisar gravar no Neo4j:** Use o `WorkerIntegrationController` para enviar nós e relacionamentos

Se você quer adicionar um novo classificador à **Rosie Engine**:

1. Crie uma nova classe em `rosie_engine.py` que herde de `BaseClassifier`
2. Implemente `fit()` e `predict()` seguindo o padrão existente
3. Adicione a instância na lista `self.classifiers` do `RosieEngine.__init__()`
4. Se quiser contabilizar no frontend, adicione o campo correspondente em `Politician.java`, `PoliticianResponseDTO.java` e na interface TypeScript em `App.tsx`

Se você quer melhorar o frontend:
1. **Novos componentes** vão em `frontend/src/components/`
2. **Novas abas** precisam: adicionar o valor no tipo do `activeTab`, criar o botão no `PoliticianCard`, e adicionar o bloco `{activeTab === 'minha_aba' && (...)}` no JSX

---

**⚠️ Aviso Legal:** Este sistema utiliza **exclusivamente** APIs Públicas e Dados Abertos protegidos pela **Lei de Acesso à Informação (LAI)**. Nenhum dado privado ou sigiloso é coletado ou armazenado.
