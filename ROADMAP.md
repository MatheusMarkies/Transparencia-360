# 🗺️ Roadmap & Board de Tarefas — Transparência 360

> **Quer contribuir?** Escolha uma tarefa abaixo, coloque seu nome no campo **Responsável** via Pull Request, e mãos à obra!
> Se não sabe por onde começar, vá direto para a seção **🟢 Tarefas para Não-Programadores**.

---

## Como Funciona Este Board

Cada tarefa tem:
- **Nível de dificuldade:** 🟢 Fácil | 🟡 Médio | 🔴 Difícil
- **Tipo:** 🐛 Bug | 🧩 Integração | 🔧 Melhoria | ✨ Feature Nova | 🔍 Validação
- **Status:** `[ ]` Aberta | `[/]` Em andamento | `[x]` Concluída
- **Responsável:** Coloque seu **@usuario** aqui ao pegar a tarefa

> **⚠️ Regra de Ouro:** Antes de começar, faça um PR adicionando seu nome no campo "Responsável" para ninguém pegar a mesma tarefa.

---

## 🔴 Bugs & Problemas Críticos

Problemas que afetam a qualidade dos dados **agora mesmo**.

### 1. 🐛 Bug: PNCPWorker sem `self` no método
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/pncp_worker.py` |
| **Problema** | O método `fetch_contracts_for_municipality()` está definido sem `self` como primeiro parâmetro. Vai crashar ao ser chamado pelo `run()`. |
| **Como corrigir** | Adicionar `self` como primeiro argumento do método (linha ~43). |
| **Dificuldade** | 🟢 Fácil (1 linha de código) |
| **Responsável** | — |

### 2. 🐛 Bug: Emendas sempre atribuídas a Lins/SP
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/emendas_gatherer.py` (linha 82) |
| **Problema** | Todas as emendas parlamentares estão sendo salvas com o código IBGE `3527108` independente do município real. Existe um `TODO` no código. |
| **Como corrigir** | Extrair o campo `localidadeDoGasto` da resposta da API do Portal da Transparência e mapear para o código IBGE correto. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 3. 🐛 Bug: Salário de assessor hardcoded em R$12.000
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/ghost_employee_worker.py` (linhas 128, 137) |
| **Problema** | O salário dos assessores parlamentares está fixo em R$12.000. O valor real varia e deveria ser extraído da API de servidores do Portal da Transparência. |
| **Como corrigir** | Integrar a busca de remuneração via endpoint `/servidores/remuneracao` da CGU. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🟡 Workers Órfãos (Existem mas NÃO rodam no Pipeline)

Esses workers estão **prontos** (ou quase) mas não foram adicionados ao `run_all_extractions.py`.

### 4. 🧩 Integrar: GhostEmployeeWorker no pipeline
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/ghost_employee_worker.py` |
| **Problema** | Detector de "Funcionários Fantasma" está 100% implementado com scraping de gabinete, cruzamento QSA e geolocalização, mas **não aparece** em `run_all_extractions.py`. |
| **Como corrigir** | Adicionar como novo `run_step()` na Fase 3 do pipeline. Testar com `--limit 5`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 5. 🧩 Integrar: TransparenciaWorker no pipeline
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/transparencia_worker.py` |
| **Problema** | Worker avulso do Portal da Transparência que não está no pipeline principal. |
| **Como corrigir** | Avaliar quais funcionalidades já estão cobertas por outros workers e integrar o que falta. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 6. 🧩 Integrar: TSEWorker no pipeline
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/tse_worker.py` |
| **Problema** | Worker avulso do TSE que não está no pipeline principal. |
| **Como corrigir** | Verificar se `etl/tse.py` já cobre tudo ou se este worker adiciona funcionalidade extra. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🟠 Workers Incompletos (Precisam de Trabalho)

Esses workers existem no pipeline mas têm funcionalidade parcial.

### 7. 🔧 Revisar: RAISWorker (LGPD) 
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rais_worker.py` |
| **Problema** | O sistema RAIS (Ministério do Trabalho) agora opera sob LGPD e **não libera mais dados públicos** como antes. O worker atual é um esqueleto que lê CSVs mas não tem fonte de dados real disponível. |
| **Ação necessária** | Pesquisar alternativas públicas (CAGED, eSocial, dados agregados do PDET) ou marcar o worker como deprecated. Documentar a limitação. |
| **Dificuldade** | 🔴 Difícil (requer pesquisa legal e de APIs) |
| **Responsável** | — |

### 8. 🔧 Completar: TCUWorker — Ingestão no banco
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/tcu_worker.py` |
| **Problema** | Busca a lista de contas irregulares do TCU corretamente, mas apenas imprime logs. **Não salva nada** no PostgreSQL via backend. |
| **Como corrigir** | Após o `fetch_ineligible_list()`, cruzar os nomes/CPFs com os políticos no banco e atualizar campos relevantes (ex: `judicialRiskScore`). |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 9. 🔧 Completar: CamaraNLPGatherer — Integrar análise
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/camara_nlp_gatherer.py` |
| **Problema** | Baixa transcrições de discursos para disco como trilha de auditoria, mas o método `analyze_zero_activity()` não é chamado no `run()` e os resultados não são enviados ao backend. |
| **Como corrigir** | No `run()`, após baixar, chamar `analyze_zero_activity()` para cada assessor do gabinete e enviar resultado via `BackendClient`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🔵 Features Novas

Funcionalidades que agregariam muito valor ao sistema.

### 10. ✨ Timeline Visual de Anomalias (Frontend)
| | |
|---|---|
| **Descrição** | Criar um componente React que mostre uma linha do tempo: *Dia 1: Doou para campanha → Dia 40: Recebeu emenda → Dia 45: Ganhou licitação* |
| **Onde** | `frontend/src/components/` (novo componente) + nova aba no `App.tsx` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 11. ✨ Data QA com Great Expectations
| | |
|---|---|
| **Descrição** | Adicionar validações automáticas antes de ingerir dados. Se a API retornar salários negativos, CPFs com 10 dígitos ou valores absurdos, o pipeline deve pausar em vez de poluir o banco. |
| **Onde** | Novo módulo `workers/src/qa/` |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 12. ✨ Mascaramento LGPD de CPFs (Backend)
| | |
|---|---|
| **Descrição** | Implementar um middleware no Spring Boot que mascare automaticamente CPFs (`***.123.456-**`) em todos os endpoints públicos do Frontend. Os workers internos continuam vendo o CPF completo. |
| **Onde** | `backend/src/main/java/com/tp360/core/` (novo filter/interceptor) |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 13. ✨ Record Linkage com Splink (Entity Resolution)
| | |
|---|---|
| **Descrição** | Resolver o problema de homônimos: "Maria da Silva que doou" é a mesma "Maria da Silva sócia da empresa"? O Splink calcula um Confidence Score probabilístico. |
| **Onde** | Novo módulo `workers/src/analyzers/entity_resolution.py` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 14. ✨ Desacoplar Queries Cypher
| | |
|---|---|
| **Descrição** | Extrair as queries Cypher complexas (ex: Triangulação, Follow The Money) que hoje estão embedadas no Java e colocá-las em arquivos `.cypher` limpos na pasta `backend/src/main/resources/queries/`. |
| **Onde** | `PoliticoNodeRepository.java` → arquivos `.cypher` externos |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🟢 Tarefas para Não-Programadores (via Antigravity)

> **Não precisa saber programar!** Basta ter o Antigravity instalado e saber rodar comandos no terminal. Essas tarefas são essenciais para a qualidade do projeto.

### 15. 🔍 Validar dados de políticos conhecidos
| | |
|---|---|
| **Descrição** | Rodar o pipeline para 5 políticos famosos (ex: presidentes da Câmara, líderes de bancada) e comparar manualmente os dados do dashboard com os sites oficiais (Câmara, TSE, Portal da Transparência). Reportar discrepâncias como Issue. |
| **Como rodar** | `python run_all_extractions.py --limit 5` e acessar `http://localhost:5173` |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 16. 🔍 Testar cada aba do Dashboard
| | |
|---|---|
| **Descrição** | Após rodar o pipeline, clicar em cada político e verificar as 6 abas: (1) Visão Geral mostra patrimônio? (2) Deep Match mostra radar? (3) Grafo mostra conexões? (4) Extrato CEAP mostra despesas? (5) Emendas mostra dados? (6) Rastreabilidade mostra fontes? Anotar o que está vazio ou quebrado. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 17. 🔍 Auditar Super Relatórios JSON
| | |
|---|---|
| **Descrição** | Abrir os JSONs gerados em `data/processed/super_reports/` e verificar se os campos fazem sentido: o patrimônio declarado bate? O score de risco parece coerente? Há campos `null` que deveriam ter dados? |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 18. 🔍 Documentar APIs instáveis do governo
| | |
|---|---|
| **Descrição** | Rodar o pipeline várias vezes em horários diferentes e anotar quais APIs falham com mais frequência (timeout, 403, 500). Criar um documento `docs/api_stability_report.md` com os achados. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 19. 🔍 Criar test cases de fraude real já julgada
| | |
|---|---|
| **Descrição** | Pesquisar casos de rachadinha, nepotismo ou desvio de emendas que já foram **julgados e condenados publicamente**. Documentar os dados do caso (quem, quando, valor, empresa envolvida) para usarmos como "gabarito" para validar se o nosso pipeline detectaria o padrão. |
| **Dificuldade** | 🟡 Médio (requer pesquisa) |
| **Responsável** | — |

### 20. 🔍 Testar pipeline em diferentes sistemas operacionais
| | |
|---|---|
| **Descrição** | Seguir o README e rodar o sistema completo em Mac, Linux ou Windows. Reportar erros de instalação, incompatibilidades de Docker, e problemas de encoding. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

---

## 📋 Resumo Rápido

| # | Tarefa | Tipo | Dificuldade | Status | Responsável |
|:--|:-------|:-----|:-----------|:-------|:------------|
| 1 | PNCPWorker bug `self` | 🐛 Bug | 🟢 | `[ ]` | — |
| 2 | Emendas IBGE hardcoded | 🐛 Bug | 🟡 | `[ ]` | — |
| 3 | Salário assessor hardcoded | 🐛 Bug | 🟡 | `[ ]` | — |
| 4 | Integrar GhostEmployeeWorker | 🧩 Integração | 🟡 | `[ ]` | — |
| 5 | Integrar TransparenciaWorker | 🧩 Integração | 🟡 | `[ ]` | — |
| 6 | Integrar TSEWorker | 🧩 Integração | 🟡 | `[ ]` | — |
| 7 | Revisar RAISWorker (LGPD) | 🔧 Melhoria | 🔴 | `[ ]` | — |
| 8 | Completar TCUWorker | 🔧 Melhoria | 🟢 | `[ ]` | — |
| 9 | Completar CamaraNLPGatherer | 🔧 Melhoria | 🟡 | `[ ]` | — |
| 10 | Timeline Visual (Frontend) | ✨ Feature | 🔴 | `[ ]` | — |
| 11 | Data QA (Great Expectations) | ✨ Feature | 🟡 | `[ ]` | — |
| 12 | Mascaramento LGPD CPFs | ✨ Feature | 🟡 | `[ ]` | — |
| 13 | Record Linkage (Splink) | ✨ Feature | 🔴 | `[ ]` | — |
| 14 | Desacoplar queries Cypher | ✨ Feature | 🟡 | `[ ]` | — |
| 15 | Validar dados de políticos | 🔍 Validação | 🟢 | `[ ]` | — |
| 16 | Testar abas do dashboard | 🔍 Validação | 🟢 | `[ ]` | — |
| 17 | Auditar Super Relatórios | 🔍 Validação | 🟢 | `[ ]` | — |
| 18 | Documentar APIs instáveis | 🔍 Validação | 🟢 | `[ ]` | — |
| 19 | Test cases de fraude real | 🔍 Validação | 🟡 | `[ ]` | — |
| 20 | Testar em diferentes OS | 🔍 Validação | 🟢 | `[ ]` | — |
| 21 | LLM: Resumo de Dossiê | 🧠 LLM | 🟡 | `[ ]` | — |
| 22 | LLM: Análise de Gazette NLP | 🧠 LLM | 🔴 | `[ ]` | — |
| 23 | LLM: Explicação de Anomalias | 🧠 LLM | 🟡 | `[ ]` | — |
| 24 | LLM: Entity Resolution semântica | 🧠 LLM | 🔴 | `[ ]` | — |
| 25 | Deploy: CI/CD + Docker Hub | 🚀 Deploy | 🟡 | `[ ]` | — |
| 26 | Deploy: Infra de Produção | 🚀 Deploy | 🔴 | `[ ]` | — |
| 27 | Deploy: Scheduler de Pipeline | 🚀 Deploy | 🟡 | `[ ]` | — |
| 28 | Worker: CamaraGatherer | 🔩 Worker | 🟡 | `[ ]` | — |
| 29 | Worker: ExpensesWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 30 | Worker: AbsencesWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 31 | Worker: WealthAnomalyWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 32 | Worker: StaffAnomalyWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 33 | Worker: RachadinhaScoringWorker | 🔩 Worker | 🔴 | `[ ]` | — |
| 34 | Worker: SpatialAnomalyWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 35 | Worker: CrossMatchOrchestrator | 🔩 Worker | 🔴 | `[ ]` | — |
| 36 | Worker: EmendasPixWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 37 | Worker: CoherenceWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 38 | Worker: GazetteGraphBuilder | 🔩 Worker | 🔴 | `[ ]` | — |
| 39 | Worker: GazetteAggregator | 🔩 Worker | 🟢 | `[ ]` | — |
| 40 | Worker: JudicialAggregator | 🔩 Worker | 🟡 | `[ ]` | — |
| 41 | Worker: DocumentaryEvidenceWorker | 🔩 Worker | 🟡 | `[ ]` | — |
| 42 | Worker: SuperReportWorker | 🔩 Worker | 🟡 | `[ ]` | — |

---

## 🔩 Otimização Individual de Workers

> **Uma pessoa por worker.** Cada worker abaixo pode ser "adotado" por um contribuidor. O objetivo é: revisar o código, testar com dados reais, identificar bugs, otimizar performance, e documentar o que o worker realmente faz vs o que deveria fazer.
>
> **O que se espera de quem adota um worker:**
> 1. Rodar o worker isoladamente e verificar a saída
> 2. Comparar os dados gerados com a fonte original (API do governo)
> 3. Identificar edge cases (políticos sem dados, APIs fora do ar, dados malformados)
> 4. Documentar limitações encontradas como comentários no código ou Issues
> 5. Propor e implementar melhorias

### 28. 🔩 CamaraGatherer — Base de Deputados
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/camara_gatherer.py` |
| **Pipeline Step** | 1 (Fase 1) |
| **O que faz** | Busca a lista de deputados ativos na API da Câmara e envia para o backend |
| **O que revisar** | Verificar se todos os campos estão sendo extraídos (foto, email, gabinete). Testar com deputados que mudaram de partido recentemente. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 29. 🔩 ExpensesWorker — Despesas CEAP
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/expenses_worker.py` |
| **Pipeline Step** | 4 (Fase 2) |
| **O que faz** | Busca despesas da Cota Parlamentar e grava no PostgreSQL + Neo4j |
| **O que revisar** | Verificar se os valores batem com o site oficial da Câmara. Testar com deputados que têm muitas despesas (>500 notas/ano). Verificar se o campo `ufFornecedor` está sempre preenchido. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 30. 🔩 AbsencesWorker — Presenças no Plenário
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/absences_worker.py` |
| **Pipeline Step** | 5 (Fase 2) |
| **O que faz** | Busca sessões plenárias e registros de presença, grava no Neo4j |
| **O que revisar** | Comparar taxa de ausência calculada com o site da Câmara. Verificar se sessões extraordinárias estão sendo contadas. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 31. 🔩 WealthAnomalyWorker — Anomalia Patrimonial
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/wealth_anomaly_worker.py` |
| **Pipeline Step** | 8 (Fase 3) |
| **O que faz** | Compara patrimônio declarado ao TSE (2014→2018→2022) com o salário de deputado |
| **O que revisar** | Verificar se o cálculo de limiar (salário × 48 meses × 100% poupança) é justo. Testar com deputados que venderam/compraram imóveis legitimamente. Considerar inflação no cálculo. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 32. 🔩 StaffAnomalyWorker — Anomalia de Gabinete (ML)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/staff_anomaly_worker.py` (13.4KB — maior worker) |
| **Pipeline Step** | 9 (Fase 3) |
| **O que faz** | Usa Isolation Forest (ML) para detectar fornecedores com padrões atípicos de pagamento |
| **O que revisar** | Validar se os alertas de `SUPER_PAGAMENTO` e `CONCENTRACAO` fazem sentido. Ajustar hiperparâmetros do Isolation Forest (contamination, n_estimators). Verificar se a média global é representativa. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 33. 🔩 RachadinhaScoringWorker — Motor de Risco (5 Heurísticas)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rachadinha_worker.py` (31.6KB — **maior arquivo do projeto**) |
| **Pipeline Step** | 10 (Fase 3) |
| **O que faz** | Calcula score de risco 0-100 usando 5 heurísticas: Doador Compulsório, Rotatividade de Laranjas, Triangulação CNPJ, Gazette NLP, Judiciário |
| **O que revisar** | Validar os pesos de cada heurística (25/20/25/15/15). Verificar se a H3 (Triangulação via BrasilAPI) está funcionando com rate limit. Testar com casos conhecidos de rachadinha. Documentar falsos positivos encontrados. |
| **Dificuldade** | 🔴 Difícil (código complexo, 611 linhas) |
| **Responsável** | — |

### 34. 🔩 SpatialAnomalyWorker — Detector de Teletransporte
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/spatial_anomaly_worker.py` |
| **Pipeline Step** | 11 (Fase 3) |
| **O que faz** | Cruza presenças em Brasília com despesas emitidas em outros estados no mesmo dia |
| **O que revisar** | Verificar se o filtro `ufFornecedor <> 'NA'` não está descartando dados válidos. Considerar fuso horário nas comparações de data. Testar se despesas de e-commerce (sem UF significativo) geram falsos positivos. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 35. 🔩 CrossMatchOrchestrator — Grafo Profundo Neo4j
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/cross_match_orchestrator.py` (15.3KB) |
| **Pipeline Step** | 12 (Fase 3) |
| **O que faz** | Orquestra 7 sub-etapas para construir o grafo de triangulação de 3º grau no Neo4j |
| **O que revisar** | Verificar se cada sub-etapa funciona independentemente. Testar o fallback quando Neo4j não está disponível (Dry Run Mode). Otimizar queries Cypher para grandes volumes. Verificar se o rate limiting das APIs externas (BrasilAPI, Querido Diário) está sendo respeitado. |
| **Dificuldade** | 🔴 Difícil (7 sub-etapas, 5 APIs externas) |
| **Responsável** | — |

### 36. 🔩 EmendasPixWorker — Fluxo Circular de Emendas
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/emendas_pix_worker.py` |
| **Pipeline Step** | 14 (Fase 3) |
| **O que faz** | Busca o ciclo completo: Político → Emenda → Prefeitura → Contrato → Empresa → Sócio → Doador → Político |
| **O que revisar** | Depende da tarefa #2 (IBGE hardcoded) para ter dados reais de municípios. Verificar se a query Cypher de ciclo funciona com dados reais. Testar com emendas de anos diferentes. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 37. 🔩 CoherenceWorker — Promessas vs Votos
| | |
|---|---|
| **Arquivo** | `workers/src/nlp/coherence_worker.py` |
| **Pipeline Step** | 16 (Fase 3) |
| **O que faz** | Compara promessas de campanha com votos no plenário usando similaridade textual |
| **O que revisar** | Verificar se o algoritmo de similaridade é suficiente (TF-IDF? Cosine?). Testar com promessas vagas tipo "melhorar a educação". Considerar usar embeddings para melhorar a precisão. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 38. 🔩 GazetteGraphBuilder — Diários Oficiais → Neo4j
| | |
|---|---|
| **Arquivos** | `workers/src/nlp/gazette_text_fetcher.py` + `gazette_nlp_extractor.py` + `gazette_neo4j_ingester.py` |
| **Pipeline Step** | 17 (Fase 3) |
| **O que faz** | Busca Diários Oficiais no Querido Diário, extrai CNPJs via NLP/RegEx, e ingere no Neo4j |
| **O que revisar** | Grupo de 3 arquivos que trabalham juntos. Verificar se os padrões RegEx cobrem todas as variações de CNPJ. Testar com diários de diferentes municípios (formatação varia muito). Otimizar o chunking de textos longos. |
| **Dificuldade** | 🔴 Difícil (3 arquivos interdependentes + NLP) |
| **Responsável** | — |

### 39. 🔩 GazetteAggregator — Consolidação Neo4j → PostgreSQL
| | |
|---|---|
| **Arquivo** | `workers/src/nlp/gazette_aggregator_worker.py` |
| **Pipeline Step** | 18 (Fase 3) |
| **O que faz** | Lê os findings do Neo4j e consolida nos campos `nlpGazetteCount` e `nlpGazetteDetails` do PostgreSQL |
| **O que revisar** | Verificar se a contagem bate com os nós reais no Neo4j. Testar se o campo `nlpGazetteDetails` não ultrapassa o limite de tamanho da coluna no PostgreSQL. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 40. 🔩 JudicialAggregator — DataJud → PostgreSQL
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/judicial_aggregator_worker.py` |
| **Pipeline Step** | 20 (Fase 3) |
| **O que faz** | Consulta 7 tribunais (TRF1-5, STJ, TST) buscando processos de improbidade |
| **O que revisar** | Verificar se todos os 7 tribunais estão respondendo. Testar com políticos que sabidamente têm processos. Verificar se o rate limiting não está causando dados incompletos. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 41. 🔩 DocumentaryEvidenceWorker — Trilha de Auditoria
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/documentary_evidence_worker.py` |
| **Pipeline Step** | 21 (Fase 3) |
| **O que faz** | Gera relatórios determinísticos (não-ML) baixando despesas do ano corrente para auditoria |
| **O que revisar** | Verificar se os JSONs gerados em `data/processed/audit_reports/` estão completos. Comparar com os dados do Super Report. Testar se o Event Loop não crasha com muitos deputados simultâneos. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 42. 🔩 SuperReportWorker — Laudo Final Unificado
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/super_report_worker.py` |
| **Pipeline Step** | 26 (Fase 3 — último step) |
| **O que faz** | Consolida TODOS os dados de um político num JSON final de auditoria |
| **O que revisar** | Verificar se todos os campos estão populados (muitos podem vir `null`). Testar se `safe_json_load()` funciona com todos os formatos de string JSON do banco. Comparar o relatório com os dados visíveis no dashboard. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |



## 🧠 Integração de LLMs nas Análises

> **Discussão em aberto:** Hoje todo o NLP do projeto é baseado em RegEx e matching textual simples. LLMs podem elevar drasticamente a qualidade das análises, mas trazem desafios de custo, privacidade e reprodutibilidade.

### Onde LLMs agregariam mais valor

O sistema atual funciona com heurísticas determinísticas (RegEx, Isolation Forest, contagens). LLMs entrariam como **camada de enriquecimento** em 4 pontos específicos:

| Ponto de Integração | Hoje (sem LLM) | Com LLM | Impacto |
|:---|:---|:---|:---|
| **Análise de Diários Oficiais** | RegEx para CNPJs e valores | Compreensão semântica: "esta dispensa de licitação beneficia a empresa X que tem vínculo com Y" | 🔴 Alto |
| **Resumo do Dossiê** | JSON técnico com scores | Texto em linguagem natural: "Este deputado apresenta 3 alertas graves..." | 🟡 Médio |
| **Explicação de Anomalias** | Score numérico (ex: risco 78/100) | Texto explicativo: "O risco é alto porque 65% dos gastos vão para 2 fornecedores que..." | 🟡 Médio |
| **Entity Resolution** | Matching exato de nomes/CPFs | Matching semântico: "Maria S. Silva" = "Maria da Silva Santos" com 92% de confiança | 🔴 Alto |

### Decisões Arquiteturais Importantes

**🔒 Privacidade (LGPD):**
- CPFs, nomes completos e dados pessoais **NÃO podem** ser enviados para APIs de LLM na nuvem (OpenAI, Anthropic, Google) sem anonimização prévia
- **Opção A:** Rodar modelos locais (Ollama + Llama 3.1, Mistral, Qwen) — grátis, privado, mas precisa de GPU
- **Opção B:** Anonimizar dados antes de enviar para API de nuvem (mascarar CPFs, trocar nomes por IDs)
- **Opção C:** Usar APIs que permitem DPA (Data Processing Agreement) — mais caro mas juridicamente seguro

**📊 Reprodutibilidade:**
- Análises baseadas em LLM **não são determinísticas** — rodar duas vezes pode dar resultados diferentes
- Solução: LLM gera apenas **texto explicativo** sobre análises já feitas pelas heurísticas determinísticas. O score numérico continua vindo do algoritmo, o LLM só "traduz" para linguagem humana

**💰 Custo:**
- APIs cloud: ~$0.01-0.10 por político (dependendo do modelo e volume de texto)
- Modelos locais (Ollama): grátis mas precisa de ≥8GB VRAM para modelos 7B quantizados

### Tarefas de LLM

### 21. 🧠 LLM: Gerador de Resumo em Linguagem Natural
| | |
|---|---|
| **Descrição** | Criar um worker que lê o Super Relatório JSON de cada político e gera um resumo de 3-5 parágrafos em português explicando os achados para leigos. Ex: *"O deputado X apresenta um crescimento patrimonial de R$2M em 4 anos, incompatível com o salário de R$44k/mês. Além disso, 65% das despesas de gabinete foram para apenas 2 fornecedores..."* |
| **Abordagem sugerida** | Ollama local com Llama 3.1 8B ou API Gemini com dados anonimizados |
| **Onde** | Novo worker `workers/src/nlp/llm_summary_worker.py` |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 22. 🧠 LLM: Análise Semântica de Diários Oficiais
| | |
|---|---|
| **Descrição** | Substituir o `gazette_nlp_extractor.py` (RegEx) por uma análise LLM que compreenda o contexto: identificar dispensas de licitação suspeitas, extrair relações entre empresas e valores, e classificar o nível de suspeição. |
| **Cuidado** | Os textos de Diários Oficiais são longos (5-50 páginas). Precisará de chunking + RAG ou modelos com contexto longo (128k tokens). |
| **Onde** | Evolução de `workers/src/nlp/gazette_nlp_extractor.py` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 23. 🧠 LLM: Explicador de Anomalias no Frontend
| | |
|---|---|
| **Descrição** | Adicionar um botão "Explicar" ao lado de cada anomalia no dashboard que chama um endpoint do backend, que por sua vez roda um prompt LLM para traduzir o JSON de evidências em texto legível. |
| **Exemplo** | Ao clicar em "Risco de Rachadinha: 78/100", aparece: *"O score é alto porque detectamos que o fornecedor 'ABC Consultoria' recebeu R$180k em 2 anos (3x acima da média), cujo sócio-administrador doou R$50k para a campanha de 2022."* |
| **Onde** | Novo endpoint no backend + componente React |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 24. 🧠 LLM: Entity Resolution Semântica
| | |
|---|---|
| **Descrição** | Usar embeddings de LLM para calcular similaridade entre nomes de pessoas/empresas quando o matching exato falha. Complementa o Splink (tarefa #13) com uma camada semântica. |
| **Exemplo** | "M. S. ALMEIDA LTDA ME" ↔ "MARIA SILVA DE ALMEIDA EIRELI" → 89% de probabilidade de ser a mesma entidade |
| **Onde** | Extensão de `workers/src/analyzers/entity_resolution.py` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

---

## 🚀 Publicação e Deploy em Produção

> **Estado atual:** O sistema roda 100% local via Docker Compose. Para torná-lo acessível publicamente, precisamos resolver hospedagem, segurança e automação do pipeline.

### Decisões Arquiteturais

**Onde hospedar:**

| Opção | Prós | Contras | Custo estimado |
|:---|:---|:---|:---|
| **VPS (Hetzner, DigitalOcean, Contabo)** | Controle total, bom custo, Docker nativo | Manutenção manual, sem auto-scaling | €10-30/mês |
| **Railway / Render** | Deploy fácil (git push), SSL automático, free tier | Limites de RAM no free tier, Neo4j pode não caber | $0-25/mês |
| **AWS ECS / GCP Cloud Run** | Auto-scaling, robusto, créditos para projetos sociais | Complexo de configurar, curva de aprendizado | $0-50/mês (com créditos) |
| **Oracle Cloud Free Tier** | 4 VMs ARM grátis PARA SEMPRE (24GB RAM total) | Interface confusa, documentação fraca | $0/mês |

**Recomendação:** Começar com **VPS simples** (Hetzner ARM 8GB por €6/mês) ou **Oracle Cloud Free Tier** para manter custo zero. Docker Compose já funciona nesses ambientes sem mudança nenhuma.

**Componentes que precisam de hospedagem separada:**
```
┌──────────────────────────────────────────────────────┐
│  PRODUÇÃO                                            │
│                                                      │
│  Frontend (React estático)                           │
│  → Vercel / Netlify / Cloudflare Pages (GRÁTIS)     │
│                                                      │
│  Backend (Spring Boot JAR)                           │
│  → VPS com Docker ou Railway                         │
│                                                      │
│  PostgreSQL                                          │
│  → Neon.tech free tier (0.5GB) ou no mesmo VPS      │
│                                                      │
│  Neo4j                                               │
│  → AuraDB free tier (200k nós) ou no mesmo VPS      │
│                                                      │
│  Pipeline (Workers Python)                           │
│  → Cron job no VPS (roda 1x por semana)             │
│                                                      │
│  LLM (futuro)                                        │
│  → Ollama no VPS com GPU ou API cloud                │
└──────────────────────────────────────────────────────┘
```

### Tarefas de Deploy

### 25. 🚀 CI/CD + Imagens Docker no Docker Hub
| | |
|---|---|
| **Descrição** | Configurar GitHub Actions para: (1) rodar lint/testes a cada PR, (2) buildar e publicar as imagens Docker no Docker Hub/GHCR a cada merge na `main`. Isso permite que qualquer pessoa rode `docker compose up` sem precisar buildar nada. |
| **Onde** | `.github/workflows/ci.yml` + `Dockerfile` do frontend |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 26. 🚀 Infraestrutura de Produção
| | |
|---|---|
| **Descrição** | Configurar um ambiente de produção com: (1) Frontend deployado em Vercel/Cloudflare Pages com domínio próprio, (2) Backend + PostgreSQL + Neo4j em VPS ou cloud, (3) HTTPS com Let's Encrypt, (4) variáveis de ambiente seguras, (5) backups automáticos do banco. |
| **Entregável** | Documento `docs/deploy_guide.md` + scripts de provisionamento |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 27. 🚀 Scheduler do Pipeline (Cron Automatizado)
| | |
|---|---|
| **Descrição** | Em produção, o pipeline `run_all_extractions.py` precisa rodar automaticamente (ex: toda segunda-feira às 3h da manhã) em vez de ser executado manualmente. Implementar via `cron` no VPS ou GitHub Actions scheduled workflow. |
| **Considerações** | O pipeline leva ~1h para 30 deputados. Para 513 deputados, estimar 8-12h. Precisa de monitoramento (alerta se falhar). |
| **Onde** | Cron job + script wrapper com notificação (Telegram/Discord webhook) |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🤝 Como Pegar Uma Tarefa

1. **Escolha** uma tarefa acima que combina com seu perfil
2. **Fork** o repositório
3. **Faça um PR** adicionando seu `@usuario` no campo "Responsável" da tarefa escolhida
4. **Implemente** a solução em uma nova branch
5. **Abra um PR** com a implementação, referenciando o número da tarefa

> 💡 **Dica:** Se você usa Antigravity, basta abrir o projeto e pedir para ele implementar a tarefa escolhida — ele já vai ter todo o contexto do sistema.
