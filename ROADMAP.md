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

## ✅ Tarefas Concluídas

> Tarefas que já foram implementadas e integradas ao pipeline.

| # | Tarefa | Tipo | Quando |
|:--|:-------|:-----|:-------|
| — | Rosie Engine (14 classificadores) integrada ao pipeline (Step 15) | ✨ Feature | Mar/2026 |
| — | RosieWorker envia contagens para o backend via `/ingest/politician` | 🐛 Bug Fix | Mar/2026 |
| — | SuperReportWorker incluindo `evidencias_rosie` no dossiê JSON | 🔧 Melhoria | Mar/2026 |
| — | AbsencesWorker refatorado com cache `resumo/detalhes` | 🔧 Melhoria | Mar/2026 |
| — | SuperReportWorker comprime anomalias BenfordLaw em resumo | 🔧 Melhoria | Mar/2026 |
| — | `rosie_engine.py` injetando `classifier_counts` no relatório | ✨ Feature | Mar/2026 |
| — | Pipeline v3.1 com 3 fases e ROSIE como Step 15 | ✨ Feature | Mar/2026 |

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

### 2. 🐛 Bug: Emendas sempre atribuídas ao Lugar Incorreto 
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

### 4. 🐛 Bug: Punishment da Rosie com `except` duplicado
| | |
|---|---|
| **Arquivo** | `workers/run_all_extractions.py` (linhas 421-424) |
| **Problema** | O bloco `push_rosie_to_backend` inlined no `step_15` tem dois `except Exception as e:` consecutivos (linhas 421 e 423), o segundo é código morto. Além disso, `json` é usado mas não importado no escopo local. |
| **Como corrigir** | Remover o `except` duplicado e adicionar `import json` no início da função `step_15`. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

---

## 🟡 Workers Comentados no Pipeline (Funcionais, precisam ser reativados)

Esses workers estão **implementados e funcionais** mas estão **comentados** em `run_all_extractions.py`. Para ativá-los, basta descomentar as linhas correspondentes.

### 5. 🧩 Reativar: WealthAnomalyWorker (Step 8)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/wealth_anomaly_worker.py` |
| **Problema** | Comentado no pipeline. Depende de dados de patrimônio do TSE pré-carregados. |
| **Como corrigir** | Descomentar `run_step_8()` em `run_all_extractions.py`, garantir que os dados TSE estão em `data/raw/tse/`, e testar com `--limit 5`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 6. 🧩 Reativar: StaffAnomalyWorker (Step 9)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/staff_anomaly_worker.py` (13.4KB, usa Isolation Forest) |
| **Problema** | Comentado no pipeline. Funciona independentemente mas precisa de dados de despesas já ingeridos. |
| **Como corrigir** | Descomentar `run_step_9()` e testar com dados reais. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 7. 🧩 Reativar: SpatialAnomalyWorker (Step 11)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/spatial_anomaly_worker.py` |
| **Problema** | Comentado no pipeline. Depende de dados de presenças e despesas já no Neo4j. |
| **Como corrigir** | Descomentar `run_step_11()` e verificar se os nós de `SessaoPlenario` e `Despesa` existem no Neo4j. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 8. 🧩 Reativar: EmendasGatherer (Step 13)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/emendas_gatherer.py` |
| **Problema** | Comentado no pipeline. Depende de `PORTAL_API_KEY` e é lento (muitas requisições). Também tem o bug #2 (IBGE hardcoded). |
| **Como corrigir** | Corrigir o bug #2 primeiro, depois descomentar `step_13()`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 9. 🧩 Reativar: EmendasPixWorker (Step 14)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/emendas_pix_worker.py` |
| **Problema** | Comentado. Depende do Step 13 (EmendasGatherer) para ter dados de emendas no Neo4j. |
| **Como corrigir** | Ativar após o Step 13 estar funcionando. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 10. 🧩 Reativar: PNCPWorker (Step 14.5)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/pncp_worker.py` |
| **Problema** | Comentado. Depende do grafo de emendas (municípios) e tem o bug #1 (falta `self`). |
| **Como corrigir** | Corrigir o bug #1, ativar Steps 13-14, e só depois descomentar este. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 11. 🧩 Reativar: CoherenceWorker (Step 16)
| | |
|---|---|
| **Arquivo** | `workers/src/nlp/coherence_worker.py` |
| **Problema** | Comentado. Compara promessas de campanha com votos usando similaridade textual. |
| **Como corrigir** | Descomentar `step_16()`. Requer dados de promessas e votos já ingeridos. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 12. 🧩 Reativar: ETLs de Dumps Massivos (Steps 7/22)
| | |
|---|---|
| **Arquivos** | `etl/tse.py`, `etl/receita_federal.py` |
| **Problema** | Comentados. Requerem downloads manuais de dumps CSV massivos (~30GB). |
| **Como corrigir** | Baixar os dumps do TSE e Receita Federal, colocar em `data/raw/tse/` e `data/raw/receita/`, e descomentar as linhas correspondentes. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🟠 Workers Complementares (Existem, precisam de trabalho)

### 13. 🧩 Integrar: GhostEmployeeWorker no pipeline
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/ghost_employee_worker.py` |
| **Problema** | Detector de "Funcionários Fantasma" está implementado com scraping de gabinete, cruzamento QSA e geolocalização, mas **não aparece** em `run_all_extractions.py`. |
| **Como corrigir** | Adicionar como novo `run_step()` na Fase 3 do pipeline. Testar com `--limit 5`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 14. 🧩 Integrar: TransparenciaWorker no pipeline
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/transparencia_worker.py` |
| **Problema** | Worker avulso do Portal da Transparência que não está no pipeline principal. |
| **Como corrigir** | Avaliar quais funcionalidades já estão cobertas pelo CrossMatchOrchestrator e integrar o que falta. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 15. 🧩 Integrar: TSEWorker no pipeline
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/tse_worker.py` |
| **Problema** | Worker avulso do TSE que não está no pipeline principal. |
| **Como corrigir** | Verificar se `etl/tse.py` já cobre tudo ou se este worker adiciona funcionalidade extra. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 16. 🔧 Revisar: RAISWorker (LGPD) 
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rais_worker.py` |
| **Problema** | O sistema RAIS (Ministério do Trabalho) agora opera sob LGPD e **não libera mais dados públicos** como antes. O worker atual é um esqueleto que lê CSVs mas não tem fonte de dados real disponível. |
| **Ação necessária** | Pesquisar alternativas públicas (CAGED, eSocial, dados agregados do PDET) ou marcar o worker como deprecated. Documentar a limitação. |
| **Dificuldade** | 🔴 Difícil (requer pesquisa legal e de APIs) |
| **Responsável** | — |

### 17. 🔧 Completar: TCUWorker — Ingestão no banco
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/tcu_worker.py` |
| **Problema** | Busca a lista de contas irregulares do TCU corretamente, mas apenas imprime logs. **Não salva nada** no PostgreSQL via backend. |
| **Como corrigir** | Após o `fetch_ineligible_list()`, cruzar os nomes/CPFs com os políticos no banco e atualizar campos relevantes (ex: `judicialRiskScore`). |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 18. 🔧 Completar: CamaraNLPGatherer — Integrar análise
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/camara_nlp_gatherer.py` |
| **Problema** | Baixa transcrições de discursos para disco como trilha de auditoria, mas o método `analyze_zero_activity()` não é chamado no `run()` e os resultados não são enviados ao backend. |
| **Como corrigir** | No `run()`, após baixar, chamar `analyze_zero_activity()` para cada assessor do gabinete e enviar resultado via `BackendClient`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🤖 Melhorias na Rosie Engine

> O Motor Rosie (`rosie_engine.py`, 14 classificadores) está funcional mas pode ser melhorado.

### 19. 🔧 Rosie: Calibrar limiares de confiança
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rosie_engine.py` |
| **Problema** | Os limiares de confiança dos classificadores (ex: `WeekendHoliday` com `confidence=0.55` para fins de semana) foram definidos heuristicamente. Precisam ser calibrados com dados reais para reduzir falsos positivos. |
| **Como corrigir** | Rodar com `--limit 100`, exportar o CSV de anomalias, e analisar manualmente quais anomalias são falsos positivos. Ajustar os limiares e re-rodar. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 20. 🔧 Rosie: Carregar blacklist CEIS/CNEP real
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rosie_engine.py` (`CNPJBlacklistClassifier`) |
| **Problema** | O classificador de blacklist aceita um set de CNPJs, mas o `RosieWorker` não carrega a lista real do Portal da Transparência. O classificador roda vazio. |
| **Como corrigir** | Baixar a lista de empresas inidôneas do Portal da Transparência (`https://api.portaldatransparencia.gov.br/api-de-dados/ceis`) e passar ao construtor do `CNPJBlacklistClassifier`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 21. 🔧 Rosie: Carregar dados de idade de empresas
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rosie_engine.py` (`CompanyAgeClassifier`) |
| **Problema** | O classificador de idade da empresa aceita datas de fundação, mas não são fornecidas. Roda sem detectar nada. |
| **Como corrigir** | Integrar com BrasilAPI (`/cnpj/v1/{cnpj}`) para buscar a data de abertura da empresa e passar ao `CompanyAgeClassifier`. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 22. ✨ Rosie: Novo classificador — Speed Anomaly entre cidades
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rosie_engine.py` (`TravelSpeedClassifier`) |
| **Problema** | O classificador de velocidade de viagem existe mas depende de coordenadas geográficas que não são fornecidas pela API da Câmara. |
| **Como corrigir** | Mapear `ufFornecedor` para coordenadas centrais de cada UF e calcular distâncias entre despesas consecutivas. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🔵 Features Novas

Funcionalidades que agregariam muito valor ao sistema.

### 23. ✨ Timeline Visual de Anomalias (Frontend)
| | |
|---|---|
| **Descrição** | Criar um componente React que mostre uma linha do tempo: *Dia 1: Doou para campanha → Dia 40: Recebeu emenda → Dia 45: Ganhou licitação* |
| **Onde** | `frontend/src/components/` (novo componente) + nova aba no `App.tsx` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 24. ✨ Data QA com Great Expectations
| | |
|---|---|
| **Descrição** | Adicionar validações automáticas antes de ingerir dados. Se a API retornar salários negativos, CPFs com 10 dígitos ou valores absurdos, o pipeline deve pausar em vez de poluir o banco. |
| **Onde** | Novo módulo `workers/src/qa/` |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 25. ✨ Mascaramento LGPD de CPFs (Backend)
| | |
|---|---|
| **Descrição** | Implementar um middleware no Spring Boot que mascare automaticamente CPFs (`***.123.456-**`) em todos os endpoints públicos do Frontend. Os workers internos continuam vendo o CPF completo. |
| **Onde** | `backend/src/main/java/com/tp360/core/` (novo filter/interceptor) |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 26. ✨ Record Linkage com Splink (Entity Resolution)
| | |
|---|---|
| **Descrição** | Resolver o problema de homônimos: "Maria da Silva que doou" é a mesma "Maria da Silva sócia da empresa"? O Splink calcula um Confidence Score probabilístico. |
| **Onde** | Novo módulo `workers/src/analyzers/entity_resolution.py` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 27. ✨ Desacoplar Queries Cypher
| | |
|---|---|
| **Descrição** | Extrair as queries Cypher complexas (ex: Triangulação, Follow The Money) que hoje estão embedadas no Java e colocá-las em arquivos `.cypher` limpos na pasta `backend/src/main/resources/queries/`. |
| **Onde** | `PoliticoNodeRepository.java` → arquivos `.cypher` externos |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 28. ✨ Painel de Anomalias Rosie no Frontend
| | |
|---|---|
| **Descrição** | Criar um componente dedicado na aba "Deep Match" para exibir os 14 classificadores da Rosie com cards individuais: nome do classificador, contagem, exemplos das anomalias encontradas. Hoje os dados estão no backend (`rosieBenfordCount` etc.) mas não há visualização rica. |
| **Onde** | `frontend/src/components/` (novo componente `RosiePanel.tsx`) |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🟢 Tarefas para Não-Programadores (via Antigravity)

> **Não precisa saber programar!** Basta ter o Antigravity instalado e saber rodar comandos no terminal. Essas tarefas são essenciais para a qualidade do projeto.

### 29. 🔍 Validar dados de políticos conhecidos
| | |
|---|---|
| **Descrição** | Rodar o pipeline para 5 políticos famosos (ex: presidentes da Câmara, líderes de bancada) e comparar manualmente os dados do dashboard com os sites oficiais (Câmara, TSE, Portal da Transparência). Reportar discrepâncias como Issue. |
| **Como rodar** | `python run_all_extractions.py --limit 5` e acessar `http://localhost:5173` |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 30. 🔍 Testar cada aba do Dashboard
| | |
|---|---|
| **Descrição** | Após rodar o pipeline, clicar em cada político e verificar as 6 abas: (1) Visão Geral mostra patrimônio? (2) Deep Match mostra radar e anomalias Rosie? (3) Grafo mostra conexões? (4) Extrato CEAP mostra despesas? (5) Emendas mostra dados? (6) Rastreabilidade mostra fontes? Anotar o que está vazio ou quebrado. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 31. 🔍 Auditar Super Relatórios JSON
| | |
|---|---|
| **Descrição** | Abrir os JSONs gerados em `data/processed/super_reports/` e verificar se as seções `metadata`, `evidencias_rosie` e `resumo` fazem sentido: as anomalias da Rosie são coerentes? O score de risco parece justo? Há campos `null` que deveriam ter dados? |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 32. 🔍 Documentar APIs instáveis do governo
| | |
|---|---|
| **Descrição** | Rodar o pipeline várias vezes em horários diferentes e anotar quais APIs falham com mais frequência (timeout, 403, 500). Criar um documento `docs/api_stability_report.md` com os achados. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 33. 🔍 Criar test cases de fraude real já julgada
| | |
|---|---|
| **Descrição** | Pesquisar casos de rachadinha, nepotismo ou desvio de emendas que já foram **julgados e condenados publicamente**. Documentar os dados do caso (quem, quando, valor, empresa envolvida) para usarmos como "gabarito" para validar se o nosso pipeline detectaria o padrão. |
| **Dificuldade** | 🟡 Médio (requer pesquisa) |
| **Responsável** | — |

### 34. 🔍 Testar pipeline em diferentes sistemas operacionais
| | |
|---|---|
| **Descrição** | Seguir o README e rodar o sistema completo em Mac, Linux ou Windows. Reportar erros de instalação, incompatibilidades de Docker, e problemas de encoding. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

### 35. 🔍 Validar anomalias Rosie com dados reais
| | |
|---|---|
| **Descrição** | Rodar o pipeline com `--limit 15`, abrir o `rosie_anomalies.csv` gerado, e verificar manualmente 20 anomalias: o gasto flagado como "fim de semana" realmente foi num sábado? A nota flagada como "duplicata" é realmente a mesma? Registrar falsos positivos. |
| **Dificuldade** | 🟢 Fácil |
| **Responsável** | — |

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

### 36. 🔩 CamaraGatherer — Base de Deputados
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/camara_gatherer.py` |
| **Pipeline Step** | 1 (Fase 1) — ✅ Ativo |
| **O que faz** | Busca a lista de deputados ativos na API da Câmara e envia para o backend |
| **O que revisar** | Verificar se todos os campos estão sendo extraídos (foto, email, gabinete). Testar com deputados que mudaram de partido recentemente. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 37. 🔩 ExpensesWorker — Despesas CEAP
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/expenses_worker.py` |
| **Pipeline Step** | 4 (Fase 2) — ✅ Ativo |
| **O que faz** | Busca despesas da Cota Parlamentar e grava no PostgreSQL + Neo4j |
| **O que revisar** | Verificar se os valores batem com o site oficial da Câmara. Testar com deputados que têm muitas despesas (>500 notas/ano). Verificar se o campo `ufFornecedor` está sempre preenchido. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 38. 🔩 AbsencesWorker — Presenças no Plenário
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/absences_worker.py` |
| **Pipeline Step** | 5 (Fase 2) — ✅ Ativo |
| **O que faz** | Busca sessões plenárias e registros de presença, grava no Neo4j. Possui cache local com estrutura resumo/detalhes. |
| **O que revisar** | Comparar taxa de ausência calculada com o site da Câmara. Verificar se sessões extraordinárias estão sendo contadas. Validar se o cache está sendo lido corretamente. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 39. 🔩 RachadinhaScoringWorker — Motor de Risco (5 Heurísticas)
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/rachadinha_worker.py` (31.6KB — **maior arquivo do projeto**) |
| **Pipeline Step** | 10 (Fase 3) — ✅ Ativo |
| **O que faz** | Calcula score de risco 0-100 usando 5 heurísticas: Doador Compulsório, Rotatividade de Laranjas, Triangulação CNPJ, Gazette NLP, Judiciário |
| **O que revisar** | Validar os pesos de cada heurística (25/20/25/15/15). Verificar se a H3 (Triangulação via BrasilAPI) está funcionando com rate limit. Testar com casos conhecidos de rachadinha. Documentar falsos positivos encontrados. |
| **Dificuldade** | 🔴 Difícil (código complexo) |
| **Responsável** | — |

### 40. 🔩 CrossMatchOrchestrator — Grafo Profundo Neo4j
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/cross_match_orchestrator.py` (15.3KB) |
| **Pipeline Step** | 12 (Fase 3) — ✅ Ativo |
| **O que faz** | Orquestra 7 sub-etapas para construir o grafo de triangulação de 3° grau no Neo4j |
| **O que revisar** | Verificar se cada sub-etapa funciona independentemente. Testar o fallback quando Neo4j não está disponível (Dry Run Mode). Otimizar queries Cypher para grandes volumes. |
| **Dificuldade** | 🔴 Difícil (7 sub-etapas, 5 APIs externas) |
| **Responsável** | — |

### 41. 🔩 RosieWorker + RosieEngine — Motor de Anomalias CEAP
| | |
|---|---|
| **Arquivos** | `workers/src/gatherers/rosie_worker.py` + `rosie_engine.py` (58KB, 14 classificadores) |
| **Pipeline Step** | 15 (Fase 3) — ✅ Ativo |
| **O que faz** | Roda 14 classificadores sobre todas as notas fiscais CEAP (Benford, Duplicatas, Outliers, etc.) e envia contagens para o backend |
| **O que revisar** | Verificar se o fluxo `rosie_engine → rosie_worker → backend` está enviando todos os 5 campos (`rosieBenfordCount` etc.) corretamente. Calibrar limiares de confiança. Testar com deputados de estados diferentes (UFs podem ter regras de subcota diferentes). |
| **Dificuldade** | 🔴 Difícil (14 classificadores, 1369 linhas) |
| **Responsável** | — |

### 42. 🔩 GazetteGraphBuilder — Diários Oficiais → Neo4j
| | |
|---|---|
| **Arquivos** | `workers/src/nlp/gazette_text_fetcher.py` + `gazette_nlp_extractor.py` + `gazette_neo4j_ingester.py` |
| **Pipeline Step** | 17 (Fase 3) — ✅ Ativo |
| **O que faz** | Busca Diários Oficiais no Querido Diário, extrai CNPJs via NLP/RegEx, e ingere no Neo4j |
| **O que revisar** | Verificar se os padrões RegEx cobrem todas as variações de CNPJ. Testar com diários de diferentes municípios (formatação varia muito). |
| **Dificuldade** | 🔴 Difícil (3 arquivos interdependentes + NLP) |
| **Responsável** | — |

### 43. 🔩 SuperReportWorker — Laudo Final Unificado
| | |
|---|---|
| **Arquivo** | `workers/src/gatherers/super_report_worker.py` |
| **Pipeline Step** | 26 (Fase 3 — último step) — ✅ Ativo |
| **O que faz** | Consolida TODOS os dados de um político num JSON final de auditoria, incluindo evidências da Rosie |
| **O que revisar** | Verificar se todos os campos estão populados (muitos podem vir `null`). Validar se a compressão das anomalias BenfordLaw está correta. Comparar o relatório com os dados visíveis no dashboard. |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 🧠 Integração de LLMs nas Análises

> **Discussão em aberto:** Hoje todo o NLP do projeto é baseado em RegEx e matching textual simples. LLMs podem elevar drasticamente a qualidade das análises, mas trazem desafios de custo, privacidade e reprodutibilidade.

### Onde LLMs agregariam mais valor

O sistema atual funciona com heurísticas determinísticas (RegEx, Isolation Forest, Chi², IQR). LLMs entrariam como **camada de enriquecimento** em 4 pontos específicos:

| Ponto de Integração | Hoje (sem LLM) | Com LLM | Impacto |
|:---|:---|:---|:---|
| **Análise de Diários Oficiais** | RegEx para CNPJs e valores | Compreensão semântica: "esta dispensa de licitação beneficia a empresa X que tem vínculo com Y" | 🔴 Alto |
| **Resumo do Dossiê** | JSON técnico com scores + Rosie | Texto em linguagem natural: "Este deputado apresenta 3 alertas graves..." | 🟡 Médio |
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

### 44. 🧠 LLM: Gerador de Resumo em Linguagem Natural
| | |
|---|---|
| **Descrição** | Criar um worker que lê o Super Relatório JSON de cada político e gera um resumo de 3-5 parágrafos em português explicando os achados para leigos. Ex: *"O deputado X apresenta um crescimento patrimonial de R$2M em 4 anos, incompatível com o salário de R$44k/mês. Além disso, a Rosie detectou 42 anomalias de Benford..."* |
| **Abordagem sugerida** | Ollama local com Llama 3.1 8B ou API Gemini com dados anonimizados |
| **Onde** | Novo worker `workers/src/nlp/llm_summary_worker.py` |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 45. 🧠 LLM: Análise Semântica de Diários Oficiais
| | |
|---|---|
| **Descrição** | Substituir o `gazette_nlp_extractor.py` (RegEx) por uma análise LLM que compreenda o contexto: identificar dispensas de licitação suspeitas, extrair relações entre empresas e valores, e classificar o nível de suspeição. |
| **Cuidado** | Os textos de Diários Oficiais são longos (5-50 páginas). Precisará de chunking + RAG ou modelos com contexto longo (128k tokens). |
| **Onde** | Evolução de `workers/src/nlp/gazette_nlp_extractor.py` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 46. 🧠 LLM: Explicador de Anomalias no Frontend
| | |
|---|---|
| **Descrição** | Adicionar um botão "Explicar" ao lado de cada anomalia no dashboard que chama um endpoint do backend, que por sua vez roda um prompt LLM para traduzir o JSON de evidências em texto legível. |
| **Exemplo** | Ao clicar em "Risco de Rachadinha: 78/100", aparece: *"O score é alto porque detectamos que o fornecedor 'ABC Consultoria' recebeu R$180k em 2 anos (3x acima da média), cujo sócio-administrador doou R$50k para a campanha de 2022."* |
| **Onde** | Novo endpoint no backend + componente React |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 47. 🧠 LLM: Entity Resolution Semântica
| | |
|---|---|
| **Descrição** | Usar embeddings de LLM para calcular similaridade entre nomes de pessoas/empresas quando o matching exato falha. Complementa o Splink (tarefa #26) com uma camada semântica. |
| **Exemplo** | "M. S. ALMEIDA LTDA ME" ↔ "MARIA SILVA DE ALMEIDA EIRELI" → 89% de probabilidade de ser a mesma entidade |
| **Onde** | Extensão de `workers/src/analyzers/entity_resolution.py` |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

---

## 🎨 Branding / Renomeação do Projeto

### 48. 🎨 Renomear o Projeto
| | |
|---|---|
| **Descrição** | Escolher um novo nome para o projeto e aplicar em todos os lugares. O nome "Transparência 360" é provisório e precisa ser atualizado para o nome definitivo. |
| **Onde alterar (Frontend):** | Título da página (`<title>` em `index.html`), header/logo no `App.tsx`, textos de boas-vindas, `package.json` (campo `name`) |
| **Onde alterar (Backend):** | `application.yml` (nome da app), `pom.xml` (artifactId/groupId), logs e banners de inicialização |
| **Onde alterar (Docs):** | `README.md`, `ROADMAP.md`, `ARQUITETURA_PIPELINE.md`, `DATA_SOURCES.md` |
| **Onde alterar (Infra):** | `docker-compose.yml` (nomes dos containers), nome do repositório GitHub |
| **Dificuldade** | 🟡 Médio (muitos arquivos para buscar e substituir) |
| **Responsável** | — |

### 49. 📢 Divulgação e Parcerias Estratégicas
| | |
|---|---|
| **Descrição** | Identificar e contatar influenciadores, políticos pró-transparência e organizações da sociedade civil que possam apoiar e divulgar a plataforma. O objetivo é ganhar visibilidade e credibilidade para atrair mais contribuidores e usuários. |
| **Alvos sugeridos** | |
| • **Influenciadores** | Perfis de fiscalização política no Twitter/X, YouTube e Instagram (ex: canais de análise política, jornalismo investigativo independente) |
| • **Políticos** | Parlamentares que já defendem publicamente pautas de transparência e combate à corrupção, de qualquer partido |
| • **Organizações** | Transparência Brasil, Open Knowledge Brasil (OKBR), Transparência Internacional, Contas Abertas |
| • **Mídia** | Jornalistas investigativos como, Folha, Estadão Dados, Agência Pública |
| **Ações concretas** | (1) Preparar um vídeo demo curto mostrando o dashboard em ação, (2) Criar um one-pager explicando o projeto|
| **Dificuldade** | 🟡 Médio (requer networking e comunicação) |
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

### Tarefas de Deploy

### 50. 🚀 CI/CD + Imagens Docker no Docker Hub
| | |
|---|---|
| **Descrição** | Configurar GitHub Actions para: (1) rodar lint/testes a cada PR, (2) buildar e publicar as imagens Docker no Docker Hub/GHCR a cada merge na `main`. |
| **Onde** | `.github/workflows/ci.yml` + `Dockerfile` do frontend |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

### 51. 🚀 Infraestrutura de Produção
| | |
|---|---|
| **Descrição** | Configurar um ambiente de produção com: (1) Frontend deployado em Vercel/Cloudflare Pages com domínio próprio, (2) Backend + PostgreSQL + Neo4j em VPS ou cloud, (3) HTTPS com Let's Encrypt, (4) variáveis de ambiente seguras, (5) backups automáticos do banco. |
| **Entregável** | Documento `docs/deploy_guide.md` + scripts de provisionamento |
| **Dificuldade** | 🔴 Difícil |
| **Responsável** | — |

### 52. 🚀 Scheduler do Pipeline (Cron Automatizado)
| | |
|---|---|
| **Descrição** | Em produção, o pipeline `run_all_extractions.py` precisa rodar automaticamente (ex: toda segunda-feira às 3h da manhã) em vez de ser executado manualmente. Implementar via `cron` no VPS ou GitHub Actions scheduled workflow. |
| **Considerações** | O pipeline leva ~6 min para 1 deputado, ~1h para 30. Para 513 deputados, estimar 8-12h. Precisa de monitoramento (alerta se falhar). |
| **Onde** | Cron job + script wrapper com notificação (Telegram/Discord webhook) |
| **Dificuldade** | 🟡 Médio |
| **Responsável** | — |

---

## 📋 Resumo Rápido

| # | Tarefa | Tipo | Dificuldade | Status |
|:--|:-------|:-----|:-----------|:-------|
| 1 | PNCPWorker bug `self` | 🐛 Bug | 🟢 | `[ ]` |
| 2 | Emendas IBGE hardcoded | 🐛 Bug | 🟡 | `[ ]` |
| 3 | Salário assessor hardcoded | 🐛 Bug | 🟡 | `[ ]` |
| 4 | Punishment Rosie `except` duplicado | 🐛 Bug | 🟢 | `[ ]` |
| 5-12 | Reativar workers comentados | 🧩 Integração | 🟡 | `[ ]` |
| 13-15 | Integrar workers órfãos | 🧩 Integração | 🟡 | `[ ]` |
| 16-18 | Workers incompletos (RAIS, TCU, NLP) | 🔧 Melhoria | 🟡-🔴 | `[ ]` |
| 19-22 | Melhorias na Rosie Engine | 🔧 Melhoria | 🟡 | `[ ]` |
| 23-28 | Features novas (Timeline, QA, Rosie UI) | ✨ Feature | 🟡-🔴 | `[ ]` |
| 29-35 | Validação e testes manuais | 🔍 Validação | 🟢 | `[ ]` |
| 36-43 | Otimização individual de workers | 🔩 Worker | 🟡-🔴 | `[ ]` |
| 44-47 | Integração de LLMs | 🧠 LLM | 🟡-🔴 | `[ ]` |
| 48-49 | Branding e divulgação | 🎨 Branding | 🟡 | `[ ]` |
| 50-52 | Deploy em produção | 🚀 Deploy | 🟡-🔴 | `[ ]` |

---

## 🤝 Como Pegar Uma Tarefa

1. **Escolha** uma tarefa acima que combina com seu perfil
2. **Fork** o repositório
3. **Faça um PR** adicionando seu `@usuario` no campo "Responsável" da tarefa escolhida
4. **Implemente** a solução em uma nova branch
5. **Abra um PR** com a implementação, referenciando o número da tarefa

> 💡 **Dica:** Se você usa Antigravity, basta abrir o projeto e pedir para ele implementar a tarefa escolhida — ele já vai ter todo o contexto do sistema.
