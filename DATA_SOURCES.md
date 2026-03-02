# 🗄️ Dicionário de Dados e APIs (Transparência 360)

Para construirmos um radar OSINT de nível governamental e cobrirmos fraudes complexas (Rachadinha, Emendas Pix, Empresas de Fachada), não precisamos reinventar a roda. Toda a informação já é pública (Lei de Acesso à Informação); o nosso trabalho é cruzar os pontos.

Abaixo está o arsenal de fontes de dados do **Transparência 360**, separadas pelo "setor do crime", com os links de documentação oficiais.

---

## 🏛️ 1. O Núcleo Político (Mandatos e Despesas)
Onde acompanhamos os passos do político, os seus gastos de cota e a sua presença física.

* **API da Câmara dos Deputados (Dados Abertos v2)**
  * **O que extraímos:** Lista de deputados, presenças no plenário (para o "Teletransporte"), despesas da Cota Parlamentar (CEAP) com links dos PDFs, frentes parlamentares e autoria de projetos.
  * **Tipo:** API REST (Paginada).
  * **Documentação:** [Swagger Câmara](https://dadosabertos.camara.leg.br/swagger/api.html)

* **API do Senado Federal**
  * **O que extraímos:** Mesma lógica da Câmara, mas para os 81 senadores (CEAPS, matérias, votações, comissões).
  * **Tipo:** API REST.
  * **Documentação:** [Portal Senado](https://legis.senado.leg.br/dadosabertos/docs/)

---

## 💰 2. O Rastro do Dinheiro (Eleições, Doações e Patrimônio)
Crucial para o nosso "Scoring de Rachadinha" e alerta de anomalia patrimonial.

* **TSE - Repositório de Dados Eleitorais**
  * **O que extraímos:** Declaração de Bens (evolução patrimonial), Doadores de Campanha (para cruzar com empresas contratadas) e Despesas da eleição.
  * **Tipo:** Dumps Massivos em CSV (ZIP).
  * **Documentação:** [Portal de Dados Abertos TSE](https://dadosabertos.tse.jus.br/)

---

## 🏢 3. A Teia Corporativa (Laranjas e Fachadas)
Se tem fraude em licitação ou nota fiscal fria, o CNPJ está aqui. É o motor do nosso Neo4j para mapear parentes e sócios (Graus 2 e 3).

* **Receita Federal do Brasil (RFB) - Base de CNPJs**
  * **O que extraímos:** Situação cadastral, data de abertura (para achar "Empresas Recém-Nascidas") e o mais importante: o **QSA (Quadro de Sócios e Administradores)**.
  * **Tipo:** Dumps Massivos em CSV (+20GB). 
  * **Documentação Oficial:** [Portal de Dados Gov.br](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj)

* **BrasilAPI (Alternativa em Tempo Real)**
  * **O que extraímos:** Consultas pontuais de QSA para evitar baixar o dump inteiro para verificações rápidas.
  * **Tipo:** API REST.
  * **Documentação:** [BrasilAPI CNPJ](https://brasilapi.com.br/docs#tag/CNPJ)

---

## 🤝 4. O Cofrão Federal (Emendas Pix, Contratos e Servidores)
Esta é a API mais robusta (e mais lenta) do governo. Necessita de chave de acesso (API Key).

* **Portal da Transparência (CGU)**
  * **O que extraímos:** Salários de servidores (identificação de Fantasmas), contratos federais, lista de PEP (Pessoas Politicamente Expostas) e CEIS/CNEP (Empresas Punidas e Inidôneas).
  * **Tipo:** API REST (Rate Limit estrito).
  * **Documentação:** [Swagger CGU](https://api.portaldatransparencia.gov.br/swagger-ui.html) *(Requer geração de token)*

* **API Transferegov / Plataforma +Brasil**
  * **O que extraímos:** Onde o "Ciclo das Emendas Pix" começa. Transferências Especiais do governo federal para municípios.
  * **Tipo:** API REST / Dumps.
  * **Documentação:** [Portal de Dados Gov](https://repositorio.dados.gov.br/)

---

## 📜 5. A Camada Oculta (Licitações Municipais)
O dinheiro das emendas federais acaba sendo desviado nas prefeituras (na ponta).

* **Querido Diário (Open Knowledge Brasil)**
  * **O que extraímos:** Raspagem e NLP de Diários Oficiais municipais. É aqui que achamos a "Dispensa de Licitação" escondida num PDF.
  * **Tipo:** API REST.
  * **Documentação:** [Docs Querido Diário](https://docs.queridodiario.ok.org.br/)

* **PNCP (Portal Nacional de Contratações Públicas)**
  * **O que extraímos:** O banco de dados unificado de licitações e contratos públicos (substituto do ComprasNet).
  * **Tipo:** API REST.
  * **Documentação:** [Swagger PNCP](https://pncp.gov.br/app/api)

---

## ⚖️ 6. A Malha Fina da Justiça e Auditoria
Para calcular o Score de Risco real e achar fichas sujas.

* **DataJud (CNJ - Conselho Nacional de Justiça)**
  * **O que extraímos:** Processos por "Improbidade Administrativa" ou "Crime Contra a Lei de Licitações" associados a um CPF/CNPJ.
  * **Tipo:** API REST / GraphQL.
  * **Documentação:** [Wiki DataJud](https://datajud-wiki.cnj.jus.br/api-publica/) *(Requer API Key pública)*

* **Tribunal de Contas da União (TCU)**
  * **O que extraímos:** Contas julgadas irregulares e inabilitados para função pública.
  * **Tipo:** API REST e Dumps JSON/CSV.
  * **Documentação:** [Portal TCU](https://dadosabertos.tcu.gov.br/)

---

## 👔 7. O Pente Fino Trabalhista (Caçador de Fantasmas)
* **RAIS / PDET (Min. do Trabalho)**
  * **O que extraímos:** Quem trabalha onde e quanto ganha. Usado para achar assessores da Câmara que têm um emprego CLT de 40h do outro lado do país.
  * **Tipo:** Dumps Massivos em FTP.
  * **Documentação:** [PDET MTE](http://pdet.mte.gov.br/microdados-rais-e-caged)

---

## 🏗️ Como Atacamos Isso na Engenharia de Dados?

Para não estourar a memória RAM do nosso servidor, separamos o consumo destas fontes em duas abordagens arquiteturais no projeto:

1. **🔥 A Caixa Quente (APIs Transacionais):** Câmara, Senado, Portal da Transparência, Querido Diário e DataJud. Executamos estas num *scheduler* (Cron) buscando extrair apenas os "deltas" (o que mudou hoje) e injetamos via chamadas REST no nosso backend Spring Boot.
2. **🧊 A Caixa Fria (Dumps Massivos via Polars/DuckDB):** TSE, Receita Federal (QSA), RAIS e TCU. Descarregamos estes ZIPs de dezenas de gigabytes periodicamente, rodamos um pipeline `Polars` para transformá-los no formato `.parquet`, e o `DuckDB` os consome localmente.
