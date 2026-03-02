# 🗺️ Roadmap e Visão Arquitetural: Transparência 360

Fala galera! O MVP do nosso radar de irregularidades está de pé e seu intuito é caçar rachadinhas, nepotismo e dispensas de licitação suspeitas. 

Tudo isso parecia muito lindo, mas fiz um teste de stress rodando o pipeline completo para apenas 10 deputados e adivinhem? Bateu 1 GB de RAM brincando kkkk. Se a gente extrapolar isso para os 513 deputados e 81 senadores, cruzando com a base histórica inteira da Receita Federal (dezenas de gigabytes) e do TSE, o nosso amado `pandas` vai chorar e a memória do servidor vai pro espaço.

Para transformar o **Transparência 360** em uma ferramenta OSINT (Inteligência de Fontes Abertas) de nível investigativo real e auditável, precisamos evoluir a nossa engenharia. 
Abaixo está o nosso roadmap. Se você quer contribuir e não sabe por onde começar, escolha uma das frentes abaixo!

---

## 🚀 Fase 1: Evolução do Motor (Performance e Custo)
Chega de estourar a memória RAM com dicionários Python gigantes. Vamos adotar a stack "Local-First".

- [ ] **Migração para Polars:** Substituir o `pandas` nos *workers* de anomalia. O Polars (escrito em Rust) processa os dumps pesados do TSE e Receita Federal numa máquina simples em segundos.
- [ ] **Adoção do DuckDB:** Usar o DuckDB localmente para rodar *queries* analíticas diretas nos ficheiros, sem precisar de subir um banco de dados pesado só para fazer cruzamentos intermediários.
- [ ] **Armazenamento em Parquet:** Parar de transitar ficheiros JSON entre os pipelines e passar a usar `.parquet` (compactado, tipado e nativo do DuckDB).

---

## 🧼 Fase 2: ETL Limpo e Governança de Dados
As APIs do governo são instáveis e frequentemente retornam lixo. Precisamos de um pipeline de qualidade inspirado no OpenSanctions.

- [ ] **Camada de Transforms Exclusiva:** Criar scripts isolados apenas para sanitização (tirar acentos, formatar datas ISO, limpar CPFs/CNPJs) *antes* da regra de negócio agir, baseando-se no modelo do repositório `br-acc`.
- [ ] **Data QA (Great Expectations):** Criar validações de integridade. Se a API retornar salários negativos ou CPFs de 10 dígitos, o pipeline faz uma pausa em vez de poluir o Neo4j.
- [ ] **Observabilidade (OpenTelemetry):** Adicionar rastreio nos pipelines para sabermos exatamente em qual etapa e em qual deputado a ingestão falhou.

---

## 🕵️ Fase 3: O Fim das Falsas Acusações (Entity Resolution)
Como provar que a "Maria da Silva" que doou na campanha é a *mesma* dona da empresa licitada, e não um homónimo?

- [ ] **Modelagem FollowTheMoney:** Parar de inventar o nosso formato JSON próprio e adotar a ontologia global do *Follow The Money* (`Pessoa`, `Empresa`, `Contrato`, `Pagamento`).
- [ ] **Record Linkage com Splink:** Implementar resolução probabilística. Quando não tivermos CPF, o Splink vai calcular um "Confidence Score" (ex: 95% de chance de ser a mesma pessoa), dando base jurídica para os alertas.
- [ ] **Mascaramento LGPD (Backend):** Implementar um *middleware* no Spring Boot que mascare os CPFs (`***.123.456-**`) automaticamente nos endpoints do Frontend.

---

## 🕸️ Fase 4: O Cérebro (Neo4j) e a UX Investigativa
O Neo4j é o coração da caçada. O Frontend precisa de se comportar como uma mesa de detetive.

- [ ] **Desacoplar Queries Cypher:** Extrair as lógicas de fraude (ex: "Triangulação de Verbas") do meio do código e colocá-las em ficheiros `.cypher` limpos e isolados na pasta `/queries` do backend.
- [ ] **Componente de Timeline (React):** O crime deixa sempre um rastro no tempo. Criar uma Linha do Tempo no Frontend (ex: *Dia 1: Doou* ➡️ *Dia 40: Recebeu Emenda* ➡️ *Dia 45: Ganhou licitação*).

---

## 🎯 Fase 5: Novos Detectores (A Caçada Final)
As regras de negócio já estão desenhadas na pasta `/docs/plans`, só falta o código rodar!

- [ ] **Detector de "Teletransporte" (Anomalia Espacial):** Cruzar os dias em que o deputado registrou presença em Brasília com notas fiscais de almoço/hotel emitidas no exato mesmo dia no seu estado de origem.
- [ ] **O Ciclo das Emendas Pix:** A query Cypher que rastreia o dinheiro saindo via Emenda Especial para uma prefeitura, que então abre "Dispensa de Licitação" para uma empresa cujo sócio é doador do próprio político.
---

## 🤝 Como Contribuir?

Quer colocar a mão na massa? É só clonar o repositório, escolher uma das *checkboxes* acima (ou dar uma olhada nas *Issues* abertas) e mandar um Pull Request. 
Seja refatorando um script, melhorando os grafos no React, ou otimizando as queries no Neo4j.
