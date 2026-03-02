# 🏗️ Arquitetura Completa do Pipeline de Dados — Transparência 360

> **Objetivo:** Documento de referência que descreve, do zero ao grafo, como os dados públicos brasileiros
> são extraídos, limpos, processados, carregados no Neo4j e consumidos pelos 9 módulos do sistema.

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Camada 1 — Extração (Ingestão de Dados Brutos)](#2-camada-1--extração)
3. [Camada 2 — Limpeza e Validação (Data QA)](#3-camada-2--limpeza-e-validação)
4. [Camada 3 — Transformação e Modelagem (Entity Resolution)](#4-camada-3--transformação-e-entity-resolution)
5. [Camada 4 — Carga no Grafo (Neo4j)](#5-camada-4--carga-no-grafo-neo4j)
6. [Camada 5 — Motores de Análise (Os 9 Módulos)](#6-camada-5--motores-de-análise)
7. [Camada 6 — API e Cache](#7-camada-6--api-e-cache)
8. [Camada 7 — Frontend e Visualização](#8-camada-7--frontend-e-visualização)
9. [Orquestração e Scheduling](#9-orquestração-e-scheduling)
10. [Modelo de Dados Neo4j (Cypher Schema)](#10-modelo-de-dados-neo4j)
11. [Mapeamento: Fonte → Módulo Consumidor](#11-mapeamento-fonte--módulo-consumidor)

---

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FONTES DE DADOS PÚBLICAS                        │
│  Câmara · Senado · TSE · Receita · CGU · Querido Diário · TCU · PNCP  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  CAMADA 1 — EXTRAÇÃO                                                    │
│  ┌──────────────────┐  ┌──────────────────┐                             │
│  │ 🔥 Caixa Quente  │  │ 🧊 Caixa Fria    │                             │
│  │ APIs REST (delta) │  │ Dumps CSV/ZIP    │                             │
│  │ Cron diário/hora  │  │ Polars + DuckDB  │                             │
│  └────────┬─────────┘  └────────┬─────────┘                             │
└───────────┼──────────────────────┼──────────────────────────────────────┘
            │                      │
            ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  CAMADA 2 — LIMPEZA + VALIDAÇÃO (Great Expectations)                    │
│  Sanitização → Tipagem → Data QA → Rejeição de registros inválidos      │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  CAMADA 3 — TRANSFORMAÇÃO + ENTITY RESOLUTION                           │
│  FollowTheMoney Schema → Splink (dedupe) → Parquet normalizado          │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  CAMADA 4 — CARGA NO GRAFO                                              │
│  neo4j-admin import (bulk) │ UNWIND/MERGE (incremental) → Neo4j 5       │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ MOTORES 1-5    │ │ MOTORES 6-9  │ │  GDS Algorithms  │
│ Rachadinha     │ │ Grafos       │ │  PageRank        │
│ Fornecedores   │ │ Patrimônio   │ │  Community Det.  │
│ NLP Diários    │ │ Dossiê       │ │  Shortest Path   │
│ Teletransporte │ │ Rastreio     │ │  Benford/HHI     │
│ Emendas Pix    │ │              │ │                  │
└───────┬────────┘ └──────┬───────┘ └────────┬─────────┘
        │                 │                  │
        └────────┬────────┴──────────────────┘
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  CAMADA 6 — FastAPI + Redis Cache (cache-aside, 512MB LRU)              │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  CAMADA 7 — FRONTEND + BOTS                                             │
│  React 19 + Vite │ React-Flow (grafos) │ Discord Bot │ Telegram Bot     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Camada 1 — Extração

A extração é dividida em duas estratégias arquiteturais baseadas na natureza da fonte.

### 2.1 Caixa Quente — APIs Transacionais (Delta Diário)

Fontes com API REST que permitem buscar apenas o que mudou. O scheduler (Cron) executa diariamente.

#### 2.1.1 Câmara dos Deputados (API v2)

```
Endpoint Base: https://dadosabertos.camara.leg.br/api/v2

Extração por Recurso:
├── GET /deputados                          → Lista completa (1x/semana)
├── GET /deputados/{id}/despesas?ano=2025   → CEAP: notas fiscais com PDFs
│   Campos-chave: cnpjCpfFornecedor, valorDocumento, urlDocumento, dataDocumento
│   Paginação: itens=100, pagina=N
│
├── GET /deputados/{id}/orgaos              → Comissões e frentes parlamentares
├── GET /eventos?dataInicio=YYYY-MM-DD      → Presenças no plenário
│   Campo-chave: dataHoraInicio, localCamara
│   → Alimenta Módulo 4: Teletransporte
│
└── GET /proposicoes?dataInicio=YYYY-MM-DD  → Projetos de lei (autoria)
```

**Script de Extração (Python — Polars):**

```python
# extractors/camara_deputados.py
import httpx
import polars as pl
from pathlib import Path

BASE = "https://dadosabertos.camara.leg.br/api/v2"
RAW_DIR = Path("data/raw/camara")
RAW_DIR.mkdir(parents=True, exist_ok=True)

async def extrair_despesas_ceap(ano: int = 2025):
    """Extrai todas as despesas CEAP de todos os deputados."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE}/deputados", params={"itens": 100, "ordem": "ASC"})
        deputados = resp.json()["dados"]

        todas_despesas = []
        for dep in deputados:
            pagina = 1
            while True:
                r = await client.get(
                    f"{BASE}/deputados/{dep['id']}/despesas",
                    params={"ano": ano, "itens": 100, "pagina": pagina, "ordem": "ASC"}
                )
                dados = r.json()["dados"]
                if not dados:
                    break
                for d in dados:
                    d["deputado_id"] = dep["id"]
                    d["deputado_nome"] = dep["nome"]
                    d["deputado_siglaPartido"] = dep.get("siglaPartido", "")
                    d["deputado_siglaUf"] = dep.get("siglaUf", "")
                todas_despesas.extend(dados)
                pagina += 1

        df = pl.DataFrame(todas_despesas)
        df.write_parquet(RAW_DIR / f"ceap_{ano}_raw.parquet")
        return df

async def extrair_presencas(data_inicio: str, data_fim: str):
    """Extrai presenças no plenário — alimenta o Módulo 4 (Teletransporte)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE}/eventos",
            params={
                "dataInicio": data_inicio,
                "dataFim": data_fim,
                "tipEvento": "Sessão Deliberativa",
                "itens": 100
            }
        )
        eventos = resp.json()["dados"]

        presencas = []
        for evento in eventos:
            r = await client.get(f"{BASE}/eventos/{evento['id']}/deputados")
            for dep in r.json()["dados"]:
                presencas.append({
                    "evento_id": evento["id"],
                    "data": evento["dataHoraInicio"][:10],
                    "local": evento.get("localCamara", {}).get("nome", "Brasília"),
                    "deputado_id": dep["id"],
                    "deputado_nome": dep.get("nome", ""),
                })

        df = pl.DataFrame(presencas)
        df.write_parquet(RAW_DIR / f"presencas_{data_inicio}_{data_fim}.parquet")
        return df
```

#### 2.1.2 Senado Federal

```
Endpoint Base: https://legis.senado.leg.br/dadosabertos

├── GET /senador/lista/atual                → Senadores ativos
├── GET /senador/{codigo}/despesas?ano=2025 → CEAPS
├── GET /materia/pesquisa                   → Projetos, relatorias
└── GET /senador/{codigo}/votacoes          → Registro de presença/voto
```

#### 2.1.3 Portal da Transparência (CGU)

```
Endpoint Base: https://api.portaldatransparencia.gov.br/api-de-dados
Header: chave-api-dados: {API_KEY}

├── GET /servidores?pagina=1                → Servidores (salários)
│   → Módulo 1: Cruzar assessores com doadores
│
├── GET /contratos?dataInicial=YYYY-MM-DD   → Contratos federais
│   → Módulo 2: Fornecedores suspeitos
│
├── GET /ceis?pagina=1                      → Empresas sancionadas (CEIS)
├── GET /cnep?pagina=1                      → Empresas punidas (CNEP)
├── GET /pep?pagina=1                       → Pessoas Politicamente Expostas
│
├── GET /cartoes-pagamento?mesExtratoInicio=YYYYMM → Cartão corporativo (CPGF)
│   → Módulo 4: Teletransporte (gastos vs presença)
│
└── GET /emendas-parlamentares?ano=2025     → Emendas Pix
    → Módulo 5: Ciclo das Emendas Pix
```

**Script de Extração (Emendas — alimenta Módulo 5):**

```python
# extractors/portal_transparencia.py
import httpx
import polars as pl
from pathlib import Path

BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"
HEADERS = {"chave-api-dados": "${CGU_API_KEY}"}
RAW_DIR = Path("data/raw/cgu")

async def extrair_emendas(ano: int = 2025):
    """Extrai emendas parlamentares — alimenta Módulo 5 (Emendas Pix)."""
    async with httpx.AsyncClient(timeout=60, headers=HEADERS) as client:
        pagina = 1
        registros = []
        while True:
            r = await client.get(
                f"{BASE}/emendas-parlamentares",
                params={"ano": ano, "pagina": pagina}
            )
            dados = r.json()
            if not dados:
                break
            registros.extend(dados)
            pagina += 1

        df = pl.DataFrame(registros)
        df.write_parquet(RAW_DIR / f"emendas_{ano}_raw.parquet")
        return df

async def extrair_servidores():
    """Extrai servidores federais — alimenta Módulo 1 (Rachadinha: assessores)."""
    async with httpx.AsyncClient(timeout=60, headers=HEADERS) as client:
        pagina = 1
        registros = []
        while True:
            r = await client.get(f"{BASE}/servidores", params={"pagina": pagina})
            dados = r.json()
            if not dados:
                break
            registros.extend(dados)
            pagina += 1

        df = pl.DataFrame(registros)
        df.write_parquet(RAW_DIR / "servidores_raw.parquet")
        return df
```

#### 2.1.4 Querido Diário (Open Knowledge Brasil)

```
Endpoint Base: https://queridodiario.ok.org.br/api

├── GET /gazettes?territory_id=3550308&since=2025-01-01
│   → Módulo 3: Scanner NLP de Diários Oficiais
│
├── GET /gazettes?querystring="dispensa de licitação"&since=2025-01-01
│   → Módulo 3: Extrair CNPJs e valores de dispensas
│
└── GET /gazettes?querystring="inexigibilidade"&since=2025-01-01
```

**Script de Extração (NLP Pipeline — alimenta Módulo 3):**

```python
# extractors/querido_diario.py
import httpx
import polars as pl
from pathlib import Path

BASE = "https://queridodiario.ok.org.br/api"
RAW_DIR = Path("data/raw/diarios")

async def extrair_dispensas_licitacao(territory_ids: list[str], desde: str):
    """Busca 'Dispensa de Licitação' e 'Inexigibilidade' nos diários municipais."""
    termos = ["dispensa de licitação", "inexigibilidade"]
    resultados = []

    async with httpx.AsyncClient(timeout=30) as client:
        for tid in territory_ids:
            for termo in termos:
                offset = 0
                while True:
                    r = await client.get(
                        f"{BASE}/gazettes",
                        params={
                            "territory_id": tid,
                            "querystring": termo,
                            "since": desde,
                            "offset": offset,
                            "size": 100
                        }
                    )
                    data = r.json()
                    gazettes = data.get("gazettes", [])
                    if not gazettes:
                        break
                    for g in gazettes:
                        for excerto in g.get("excerts", []):
                            resultados.append({
                                "territory_id": tid,
                                "territory_name": g.get("territory_name", ""),
                                "date": g["date"],
                                "tipo_busca": termo,
                                "excerto": excerto,
                                "url_diario": g.get("url", ""),
                            })
                    offset += 100

    df = pl.DataFrame(resultados)
    df.write_parquet(RAW_DIR / f"dispensas_{desde}_raw.parquet")
    return df
```

#### 2.1.5 TransfereGov / +Brasil e PNCP

```
TransfereGov:
├── Transferências Especiais (Emendas Pix)
│   Campos: nrEmenda, nomeAutor, codigoIBGE, valorRepasse, cnpjFavorecido
│   → Módulo 5: Deputado → Prefeitura

PNCP (https://pncp.gov.br/api):
├── GET /pncp/v1/orgaos/{cnpj}/compras?dataInicial=YYYY-MM-DD
│   → Módulo 5: Licitação na ponta
└── GET /pncp/v1/orgaos/{cnpj}/compras/{sequencial}/resultados
    → Módulo 5: Quem venceu a licitação
```

### 2.2 Caixa Fria — Dumps Massivos (Polars + DuckDB)

#### 2.2.1 Receita Federal — Base de CNPJs (53.6M empresas)

```
Fonte: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj
Formato: CSVs em ZIP (~20-60GB descompactado)

Arquivos:
├── Empresas*.csv        → CNPJ base, razão social, porte
├── Estabelecimentos*.csv → Filiais, endereço, CNAE, data abertura
├── Socios*.csv          → QSA: CNPJ → Sócio (alimenta Módulo 6: Deep Proxy)
└── Simples*.csv         → Optante pelo Simples/MEI
```

**Pipeline de Processamento (Polars):**

```python
# etl/receita_federal.py
import polars as pl
from pathlib import Path

RAW_DIR = Path("data/raw/receita")
CLEAN_DIR = Path("data/clean/receita")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

def processar_socios():
    """Processa QSA — coração do Deep Proxy Mapping (Módulo 6)."""
    df = pl.scan_csv(
        RAW_DIR / "Socios*.csv",
        separator=";", encoding="latin1", has_header=False,
        new_columns=[
            "cnpj_basico", "identificador_socio", "nome_socio",
            "cpf_cnpj_socio", "qualificacao_socio", "data_entrada",
            "pais", "representante_legal", "nome_representante",
            "qualificacao_representante", "faixa_etaria"
        ]
    ).with_columns([
        pl.col("cnpj_basico").str.strip_chars(),
        pl.col("nome_socio").str.strip_chars().str.to_uppercase(),
        pl.col("cpf_cnpj_socio").str.strip_chars().str.replace_all(r"[.\-/]", ""),
    ]).filter(
        pl.col("cnpj_basico").str.len_chars() >= 8
    ).collect()
    df.write_parquet(CLEAN_DIR / "socios_clean.parquet")
    return df

def processar_empresas():
    """Processa empresas — identifica 'recém-nascidas' (Módulo 2)."""
    df = pl.scan_csv(
        RAW_DIR / "Empresas*.csv",
        separator=";", encoding="latin1", has_header=False,
        new_columns=[
            "cnpj_basico", "razao_social", "natureza_juridica",
            "qualificacao_responsavel", "capital_social", "porte_empresa",
            "ente_federativo"
        ]
    ).with_columns([
        pl.col("cnpj_basico").str.strip_chars(),
        pl.col("razao_social").str.strip_chars().str.to_uppercase(),
        pl.col("capital_social").str.replace(",", ".").cast(pl.Float64, strict=False),
    ]).collect()
    df.write_parquet(CLEAN_DIR / "empresas_clean.parquet")
    return df

def processar_estabelecimentos():
    """Processa estabelecimentos — data de abertura e geolocalização."""
    df = pl.scan_csv(
        RAW_DIR / "Estabelecimentos*.csv",
        separator=";", encoding="latin1", has_header=False,
        new_columns=[
            "cnpj_basico", "cnpj_ordem", "cnpj_dv", "identificador_matriz",
            "nome_fantasia", "situacao_cadastral", "data_situacao",
            "motivo_situacao", "nome_cidade_exterior", "pais",
            "data_inicio_atividade", "cnae_fiscal_principal", "cnae_fiscal_secundaria",
            "tipo_logradouro", "logradouro", "numero", "complemento",
            "bairro", "cep", "uf", "municipio",
            "ddd1", "telefone1", "ddd2", "telefone2",
            "ddd_fax", "fax", "email"
        ]
    ).with_columns([
        (pl.col("cnpj_basico").str.strip_chars()
         + pl.col("cnpj_ordem").str.strip_chars()
         + pl.col("cnpj_dv").str.strip_chars()
        ).alias("cnpj_completo"),
    ]).collect()
    df.write_parquet(CLEAN_DIR / "estabelecimentos_clean.parquet")
    return df
```

#### 2.2.2 TSE — Dados Eleitorais

```
Fonte: https://dadosabertos.tse.jus.br/
Formato: CSVs em ZIP (~1.7GB para 2022+2024)

├── consulta_cand_*.csv      → Candidaturas (Módulo 7, 8)
├── bem_candidato_*.csv      → Declaração de bens (Módulo 7)
├── receitas_candidatos_*.csv → Doações recebidas (Módulo 1, 5, 6)
└── despesas_candidatos_*.csv → Gastos de campanha (Módulo 8)
```

```python
# etl/tse.py
import polars as pl
from pathlib import Path

RAW_DIR = Path("data/raw/tse")
CLEAN_DIR = Path("data/clean/tse")

def processar_doacoes(ano: int):
    """Processa doações. Alimenta: Módulo 1, 5, 6."""
    df = pl.scan_csv(
        RAW_DIR / f"receitas_candidatos_{ano}.csv",
        separator=";", encoding="latin1",
    ).select([
        "SQ_CANDIDATO", "NR_CPF_CNPJ_DOADOR", "NM_DOADOR",
        "VR_RECEITA", "DS_FONTE_RECEITA", "DT_RECEITA",
    ]).with_columns([
        pl.col("NR_CPF_CNPJ_DOADOR").str.replace_all(r"[.\-/]", "").alias("doc_doador_limpo"),
        pl.col("VR_RECEITA").str.replace(",", ".").cast(pl.Float64, strict=False),
        pl.col("NM_DOADOR").str.to_uppercase(),
    ]).collect()
    df.write_parquet(CLEAN_DIR / f"doacoes_{ano}_clean.parquet")
    return df

def processar_bens(ano: int):
    """Processa declaração de bens. Alimenta: Módulo 7."""
    df = pl.scan_csv(
        RAW_DIR / f"bem_candidato_{ano}.csv",
        separator=";", encoding="latin1",
    ).select([
        "SQ_CANDIDATO", "DS_TIPO_BEM_CANDIDATO", "VR_BEM_CANDIDATO",
    ]).with_columns([
        pl.col("VR_BEM_CANDIDATO").str.replace(",", ".").cast(pl.Float64, strict=False),
    ]).collect()
    df.write_parquet(CLEAN_DIR / f"bens_{ano}_clean.parquet")
    return df
```

#### 2.2.3 RAIS/CAGED (Ministério do Trabalho)

```
Fonte: http://pdet.mte.gov.br/microdados-rais-e-caged
Uso:
├── RAIS Vínculos → Módulo 1: Assessor com CLT paralelo (Fantasma)
│                  → Módulo 2: Empresa com 0 funcionários ganhando licitação
└── CAGED         → Módulo 1: Porta Giratória (taxa de demissões)
```

---

## 3. Camada 2 — Limpeza e Validação

### 3.1 Pipeline de Sanitização

```python
# transforms/sanitize.py
import re
from unidecode import unidecode

def sanitizar_cpf_cnpj(valor: str) -> str | None:
    limpo = re.sub(r"[.\-/\s]", "", str(valor))
    if len(limpo) in (11, 14):
        return limpo
    return None

def sanitizar_nome(nome: str) -> str:
    nome = unidecode(str(nome).upper().strip())
    nome = re.sub(r"\s+", " ", nome)
    nome = re.sub(r"[^\w\s]", "", nome)
    return nome

def sanitizar_valor_monetario(valor) -> float | None:
    if valor is None:
        return None
    s = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None
```

### 3.2 Validação com Great Expectations

```python
# qa/expectations.py
import great_expectations as gx

def validar_despesas_ceap(df_path: str):
    context = gx.get_context()
    suite = context.add_expectation_suite("ceap_quality")

    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(
        column="valorDocumento", min_value=0, max_value=500_000))

    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(
        column="cnpjCpfFornecedor", min_value=11, max_value=14))

    suite.add_expectation(gx.expectations.ExpectCompoundColumnsToBeUnique(
        column_list=["deputado_id", "dataDocumento", "cnpjCpfFornecedor", "valorDocumento"]))

    return suite
```

### 3.3 Regras de QA por Fonte

| Fonte | Regra | Ação se Falhar |
|---|---|---|
| CEAP (Câmara) | Valor entre R$0 e R$500k | Quarentena + log |
| TSE Doações | CPF/CNPJ com 11 ou 14 dígitos | Rejeitar registro |
| Receita QSA | Nome do sócio não-nulo | Rejeitar vínculo |
| CGU Servidores | Salário > 0 e < R$100k | Quarentena + log |
| Querido Diário | Texto com pelo menos 50 chars | Ignorar excerto |
| Emendas | Valor empenhado > 0 | Rejeitar registro |

---

## 4. Camada 3 — Transformação e Entity Resolution

### 4.1 Ontologia FollowTheMoney (Adaptada)

```
Entidades:
├── Pessoa       → CPF (mascarado), nome, UF
├── Politico     → extends Pessoa: cargo, partido, legislatura
├── Empresa      → CNPJ, razão social, data_abertura, CNAE, situação
├── Contrato     → número, objeto, valor, data, modalidade
├── Despesa      → CEAP: valor, data, tipo, URL do PDF
├── Doacao       → valor, data, tipo (PF/PJ), eleição
├── Emenda       → número, valor, autor, município destino
├── Licitacao    → objeto, modalidade, valor estimado, município
├── Sancao       → tipo (CEIS/CNEP/TCU), data, motivo
├── BemDeclarado → tipo, valor, descrição, ano eleição
└── DiarioOficial → município, data, tipo_ato, excerto

Relacionamentos:
├── (:Politico)-[:GASTOU_CEAP]->(:Despesa)-[:PAGA_A]->(:Empresa)
├── (:Empresa)-[:TEM_SOCIO]->(:Pessoa)
├── (:Pessoa)-[:DOOU_PARA]->(:Politico)           ← CICLO CHAVE
├── (:Politico)-[:AUTOR_EMENDA]->(:Emenda)
├── (:Emenda)-[:TRANSFERIU_PARA]->(:Municipio)
├── (:Municipio)-[:CONTRATOU]->(:Empresa)
├── (:Empresa)-[:VENCEU_LICITACAO]->(:Licitacao)
├── (:Empresa)-[:TEM_SANCAO]->(:Sancao)
├── (:Pessoa)-[:DECLAROU_BEM]->(:BemDeclarado)
├── (:Politico)-[:PRESENTE_EM {data, local}]->(:Sessao)
└── (:Empresa)-[:CITADA_EM]->(:DiarioOficial)
```

### 4.2 Entity Resolution com Splink

```python
# entity_resolution/resolve_pessoas.py
import splink.duckdb.linker as linker
from splink.duckdb.comparison_library import (
    jaro_winkler_at_thresholds, exact_match,
)

settings = {
    "link_type": "dedupe_only",
    "comparisons": [
        jaro_winkler_at_thresholds("nome_normalizado", [0.9, 0.7]),
        exact_match("uf"),
        exact_match("cpf_parcial", term_frequency_adjustments=True),
    ],
    "blocking_rules_to_generate_predictions": [
        "l.nome_normalizado_soundex = r.nome_normalizado_soundex",
        "l.uf = r.uf AND substr(l.nome_normalizado,1,5) = substr(r.nome_normalizado,1,5)",
    ],
    "max_iterations": 10,
}

def resolver_entidades(df_pessoas):
    """
    Dedupe: 'MARIA DA SILVA' (TSE) ↔ 'MARIA D SILVA' (QSA)
    → match_probability: 0.93 → MERGE no Neo4j
    """
    link = linker.DuckDBLinker(df_pessoas, settings)
    link.estimate_u_using_random_sampling(max_pairs=1e7)
    link.estimate_parameters_using_expectation_maximisation("l.uf = r.uf")
    return link.predict(threshold_match_probability=0.85).as_pandas_dataframe()
```

### 4.3 Parquets Prontos para Carga

```
data/ready/
├── nodes/
│   ├── politicos.parquet     → id, nome, partido, uf, cargo
│   ├── empresas.parquet      → cnpj, razao_social, data_abertura, cnae
│   ├── pessoas.parquet       → entity_id, nome, uf (pós-dedupe)
│   ├── despesas.parquet      → id, politico_id, cnpj_fornecedor, valor, data, url_pdf
│   ├── doacoes.parquet       → id, doador_id, candidato_id, valor, data
│   ├── emendas.parquet       → id, autor_id, municipio_ibge, valor
│   ├── licitacoes.parquet    → id, municipio_ibge, cnpj_vencedor, valor
│   ├── bens.parquet          → id, candidato_id, tipo, valor, ano_eleicao
│   ├── sancoes.parquet       → id, cnpj, tipo, data, motivo
│   └── diarios.parquet       → id, municipio_ibge, data, excerto, cnpjs_extraidos
│
└── relationships/
    ├── gastou_ceap.parquet       → politico_id, despesa_id
    ├── paga_a.parquet            → despesa_id, cnpj_empresa
    ├── tem_socio.parquet         → cnpj_empresa, pessoa_id, qualificacao
    ├── doou_para.parquet         → doador_id, candidato_id, valor, data
    ├── autor_emenda.parquet      → politico_id, emenda_id
    ├── transferiu_para.parquet   → emenda_id, municipio_ibge
    ├── venceu_licitacao.parquet  → cnpj_empresa, licitacao_id
    ├── tem_sancao.parquet        → cnpj_empresa, sancao_id
    ├── declarou_bem.parquet      → candidato_id, bem_id
    └── citada_em.parquet         → cnpj_empresa, diario_id
```

---

## 5. Camada 4 — Carga no Grafo (Neo4j)

### 5.1 Carga em Massa (neo4j-admin import)

```bash
#!/bin/bash
# scripts/bulk_import.sh
NEO4J_HOME=/var/lib/neo4j
sudo systemctl stop neo4j

python scripts/parquet_to_neo4j_csv.py

$NEO4J_HOME/bin/neo4j-admin database import full \
  --nodes=Empresa=data/neo4j_csv/empresas_header.csv,data/neo4j_csv/empresas.csv \
  --nodes=Pessoa=data/neo4j_csv/pessoas_header.csv,data/neo4j_csv/pessoas.csv \
  --nodes=Politico=data/neo4j_csv/politicos_header.csv,data/neo4j_csv/politicos.csv \
  --nodes=Despesa=data/neo4j_csv/despesas_header.csv,data/neo4j_csv/despesas.csv \
  --nodes=Doacao=data/neo4j_csv/doacoes_header.csv,data/neo4j_csv/doacoes.csv \
  --relationships=TEM_SOCIO=data/neo4j_csv/tem_socio_header.csv,data/neo4j_csv/tem_socio.csv \
  --relationships=GASTOU_CEAP=data/neo4j_csv/gastou_ceap_header.csv,data/neo4j_csv/gastou_ceap.csv \
  --relationships=PAGA_A=data/neo4j_csv/paga_a_header.csv,data/neo4j_csv/paga_a.csv \
  --relationships=DOOU_PARA=data/neo4j_csv/doou_para_header.csv,data/neo4j_csv/doou_para.csv \
  --skip-bad-relationships=true \
  --skip-duplicate-nodes=true \
  neo4j

sudo systemctl start neo4j
```

### 5.2 Carga Incremental (Cypher MERGE)

```cypher
// scripts/cypher/merge_despesas.cypher
UNWIND $batch AS row
MERGE (d:Despesa {id: row.id})
SET d.valor = toFloat(row.valor), d.data = date(row.data),
    d.tipo = row.tipoDespesa, d.url_pdf = row.urlDocumento, d.updated_at = datetime()

WITH d, row
MATCH (p:Politico {id_camara: row.deputado_id})
MERGE (p)-[:GASTOU_CEAP]->(d)

WITH d, row
WHERE row.cnpj_fornecedor IS NOT NULL
MERGE (e:Empresa {cnpj: row.cnpj_fornecedor})
ON CREATE SET e.razao_social = row.nomeFornecedor
MERGE (d)-[:PAGA_A]->(e);
```

```python
# loaders/neo4j_loader.py
from neo4j import GraphDatabase
import polars as pl

class Neo4jLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def carregar_batch(self, query_path: str, parquet_path: str, batch_size: int = 5000):
        df = pl.read_parquet(parquet_path)
        registros = df.to_dicts()
        with open(query_path) as f:
            query = f.read()
        with self.driver.session() as session:
            for i in range(0, len(registros), batch_size):
                session.run(query, batch=registros[i:i + batch_size])
```

### 5.3 Índices e Constraints

```cypher
// scripts/cypher/indexes.cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Empresa) REQUIRE e.cnpj IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Politico) REQUIRE p.id_camara IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Despesa) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (em:Emenda) REQUIRE em.id IS UNIQUE;

CREATE INDEX IF NOT EXISTS FOR (e:Empresa) ON (e.data_abertura);
CREATE INDEX IF NOT EXISTS FOR (d:Despesa) ON (d.data);
CREATE INDEX IF NOT EXISTS FOR (d:Doacao) ON (d.data);
CREATE INDEX IF NOT EXISTS FOR (p:Pessoa) ON (p.nome);

CREATE FULLTEXT INDEX IF NOT EXISTS pessoaFulltext FOR (p:Pessoa) ON EACH [p.nome];
CREATE FULLTEXT INDEX IF NOT EXISTS empresaFulltext FOR (e:Empresa) ON EACH [e.razao_social, e.nome_fantasia];
```

---

## 6. Camada 5 — Motores de Análise

### Módulo 1 — Radar de Rachadinha (Scoring Engine)

```cypher
// queries/modulo1_rachadinha.cypher

// 1. DOADOR COMPULSÓRIO: assessor doa % irreal do salário de volta
MATCH (pol:Politico)-[:TEM_ASSESSOR]->(ass:Pessoa)-[d:DOOU_PARA]->(pol)
WHERE d.valor > ass.salario * 0.1
RETURN pol.nome AS politico, ass.nome AS assessor,
       round(d.valor / ass.salario * 100, 1) AS pct_salario_doado
ORDER BY pct_salario_doado DESC;

// 2. PORTA GIRATÓRIA: taxa anormal de demissões
MATCH (pol:Politico)-[:TEM_ASSESSOR]->(ass:Pessoa)
WHERE ass.data_saida IS NOT NULL
WITH pol, count(ass) AS total_demitidos,
     duration.inMonths(min(ass.data_entrada), max(ass.data_saida)).months AS meses
WHERE total_demitidos > 10 AND meses < 24
RETURN pol.nome, total_demitidos, round(toFloat(total_demitidos)/meses*12, 1) AS demissoes_por_ano;

// 3. TRIANGULAÇÃO: CEAP paga empresa cujo sócio é assessor
MATCH (pol:Politico)-[:GASTOU_CEAP]->(desp:Despesa)-[:PAGA_A]->(emp:Empresa)
      -[:TEM_SOCIO]->(socio:Pessoa)<-[:TEM_ASSESSOR]-(pol)
RETURN pol.nome, emp.cnpj, socio.nome AS assessor_socio, sum(desp.valor) AS total_pago
ORDER BY total_pago DESC;
```

**Cálculo do Índice de Risco (Python):**

```python
# engines/modulo1_rachadinha.py
def calcular_indice_risco(politico_id: str, neo4j_session) -> dict:
    """Índice de Risco (0-100). Pesos: Doador(40), Porta(30), Triangulação(30)."""
    r1 = neo4j_session.run(QUERY_DOADOR, politico_id=politico_id).data()
    score_doador = min(len(r1) / max(total_assessores, 1) * 400, 100)

    r2 = neo4j_session.run(QUERY_PORTA, politico_id=politico_id).single()
    score_porta = min((r2["demissoes_por_ano"] if r2 else 0) * 5, 100)

    r3 = neo4j_session.run(QUERY_TRIANGULACAO, politico_id=politico_id).data()
    total_triangulado = sum(r["total_pago"] for r in r3)
    score_triangulacao = min(total_triangulado / 100_000 * 100, 100)

    indice = (score_doador * 0.4) + (score_porta * 0.3) + (score_triangulacao * 0.3)

    return {
        "politico_id": politico_id,
        "indice_risco": round(indice, 1),
        "score_doador_compulsorio": round(score_doador, 1),
        "score_porta_giratoria": round(score_porta, 1),
        "score_triangulacao": round(score_triangulacao, 1),
        "detalhes_doadores": r1,
        "detalhes_triangulacao": r3,
    }
```

### Módulo 2 — Fornecedores Suspeitos (ML + Heurísticas)

```python
# engines/modulo2_fornecedores.py
from sklearn.ensemble import IsolationForest
import polars as pl

def detectar_anomalias_fornecedores(despesas_df: pl.DataFrame) -> pl.DataFrame:
    features = despesas_df.group_by("cnpj_fornecedor").agg([
        pl.col("valor").sum().alias("total_recebido"),
        pl.col("valor").mean().alias("ticket_medio"),
        pl.col("valor").count().alias("num_notas"),
        pl.col("deputado_id").n_unique().alias("num_deputados_distintos"),
    ])

    X = features.select(["total_recebido", "ticket_medio", "num_notas"]).to_numpy()
    iso = IsolationForest(contamination=0.05, random_state=42)
    features = features.with_columns(
        pl.Series("anomaly_score", iso.fit_predict(X))
    )

    # HHI por gabinete (concentração)
    hhi = (despesas_df
        .group_by(["deputado_id", "cnpj_fornecedor"])
        .agg(pl.col("valor").sum().alias("total"))
        .with_columns((pl.col("total") / pl.col("total").sum().over("deputado_id")).alias("share"))
        .with_columns((pl.col("share") ** 2).alias("share_sq"))
        .group_by("deputado_id")
        .agg(pl.col("share_sq").sum().alias("hhi"))
    )

    return features.filter(
        (pl.col("anomaly_score") == -1) | (pl.col("num_deputados_distintos") == 1)
    )
```

### Módulo 3 — Scanner NLP de Diários Oficiais

```python
# engines/modulo3_nlp_diarios.py
import re, spacy
nlp = spacy.load("pt_core_news_lg")
REGEX_CNPJ = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
REGEX_VALOR = re.compile(r"R\$\s*[\d.,]+")

def extrair_entidades_diario(excerto: str) -> dict:
    cnpjs = [re.sub(r"[.\-/]", "", m) for m in REGEX_CNPJ.findall(excerto)]
    valores_raw = REGEX_VALOR.findall(excerto)
    valores = []
    for v in valores_raw:
        try:
            valores.append(float(v.replace("R$","").replace(" ","").replace(".","").replace(",",".")))
        except ValueError:
            pass

    doc = nlp(excerto)
    orgs = list(set(ent.text for ent in doc.ents if ent.label_ == "ORG"))

    eh_dispensa = bool(re.search(r"dispensa\s+de\s+licita", excerto, re.IGNORECASE))
    eh_inexig = bool(re.search(r"inexigibilidade", excerto, re.IGNORECASE))

    score = 0
    if eh_dispensa or eh_inexig: score += 20
    if len(cnpjs) == 0 and valores: score += 30
    if any(v > 100_000 for v in valores): score += 20
    if len(cnpjs) == 1: score += 10

    return {"cnpjs": cnpjs, "valores": valores, "organizacoes": orgs,
            "score_suspeicao": min(score, 100)}
```

### Módulo 4 — Teletransporte (Anomalias Espaciais)

```cypher
// queries/modulo4_teletransporte.cypher
MATCH (pol:Politico)-[:PRESENTE_EM]->(sessao:Sessao)
WHERE sessao.local = 'Brasília'
WITH pol, sessao.data AS data_sessao

MATCH (pol)-[:GASTOU_CEAP]->(desp:Despesa)-[:PAGA_A]->(emp:Empresa)
WHERE desp.data = data_sessao
  AND emp.uf <> 'DF'
  AND emp.uf = pol.uf_origem
  AND desp.tipo IN ['ALIMENTAÇÃO', 'HOSPEDAGEM', 'COMBUSTÍVEIS']

RETURN pol.nome AS politico, pol.partido, data_sessao AS data,
       desp.tipo, desp.valor, emp.razao_social, emp.uf, desp.url_pdf
ORDER BY data_sessao DESC;
```

### Módulo 5 — Ciclo das Emendas Pix

```cypher
// queries/modulo5_emendas_pix.cypher
// QUERY DEFINITIVA: rastreia o ciclo completo

MATCH (pol:Politico)-[:AUTOR_EMENDA]->(em:Emenda)-[:TRANSFERIU_PARA]->(mun:Municipio)
MATCH (mun)-[:CONTRATOU]->(emp:Empresa)
MATCH (emp)-[:TEM_SOCIO]->(socio:Pessoa)
MATCH (socio)-[doacao:DOOU_PARA]->(pol)

RETURN pol.nome AS deputado, pol.partido, em.valor AS valor_emenda,
       mun.nome AS municipio, emp.cnpj, emp.razao_social,
       socio.nome AS socio_doador, doacao.valor AS valor_doacao
ORDER BY em.valor DESC;
```

### Módulo 6 — Deep Proxy Mapping (Teias de 3º Grau)

```cypher
// queries/modulo6_deep_proxy.cypher
// Rota completa: Deputado→CEAP→Empresa A→Sócio X→Empresa B→Doador
MATCH path = (pol:Politico)-[:GASTOU_CEAP]->(:Despesa)-[:PAGA_A]->(empA:Empresa)
             -[:TEM_SOCIO]->(socioX:Pessoa)-[:TEM_SOCIO]-(empB:Empresa)
             <-[:DOOU_PARA|VENCEU_LICITACAO*1..2]-(pol)
RETURN path LIMIT 50;

// GDS: PageRank
CALL gds.pageRank.stream('transparency-graph', {maxIterations: 20, dampingFactor: 0.85})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score WHERE score > 0.1
RETURN labels(node) AS tipo, node.nome, node.cnpj, score ORDER BY score DESC LIMIT 100;

// GDS: Community Detection (Louvain)
CALL gds.louvain.stream('transparency-graph')
YIELD nodeId, communityId
WITH communityId, collect(gds.util.asNode(nodeId)) AS membros, count(*) AS tamanho
WHERE tamanho > 5
RETURN communityId, tamanho,
       [m IN membros | coalesce(m.nome, m.razao_social)] AS entidades
ORDER BY tamanho DESC LIMIT 20;
```

### Módulo 7 — Evolução Patrimonial

```cypher
// queries/modulo7_patrimonio.cypher
MATCH (pol:Politico)-[:DECLAROU_BEM]->(b:BemDeclarado)
WITH pol, b.ano_eleicao AS ano, sum(b.valor) AS patrimonio_total
ORDER BY ano
WITH pol, collect({ano: ano, patrimonio: patrimonio_total}) AS historico
WHERE size(historico) >= 2

UNWIND range(1, size(historico)-1) AS i
WITH pol,
     historico[i-1].patrimonio AS patrimonio_anterior,
     historico[i].patrimonio AS patrimonio_atual,
     (historico[i].ano - historico[i-1].ano) * 174000 * 0.7 AS max_poupavel

WHERE (patrimonio_atual - patrimonio_anterior) > max_poupavel * 2

RETURN pol.nome, pol.partido,
       patrimonio_anterior, patrimonio_atual,
       patrimonio_atual - patrimonio_anterior AS crescimento,
       round(toFloat(patrimonio_atual - patrimonio_anterior) / max_poupavel, 1) AS fator_anomalia
ORDER BY fator_anomalia DESC;
```

### Módulo 8 — Dossiê e Ranking

```cypher
// queries/modulo8_dossie.cypher
MATCH (pol:Politico)
OPTIONAL MATCH (pol)-[:GASTOU_CEAP]->(desp:Despesa)
WITH pol, sum(desp.valor) AS total_ceap, count(desp) AS num_despesas
OPTIONAL MATCH (pol)-[:PRESENTE_EM]->(s:Sessao)
WITH pol, total_ceap, num_despesas, count(s) AS presencas
OPTIONAL MATCH (pol)-[:AUTOR_EMENDA]->(em:Emenda)
WITH pol, total_ceap, num_despesas, presencas, sum(em.valor) AS total_emendas

RETURN pol.nome, pol.partido, pol.uf_origem,
       total_ceap, num_despesas, presencas, total_emendas,
       pol.salario_anual + total_ceap + coalesce(pol.auxilio_moradia, 0) AS custo_total
ORDER BY custo_total DESC;
```

### Módulo 9 — Rastreabilidade

```
Campos obrigatórios em TODA entidade do grafo:
├── fonte_oficial     → "camara_api_v2" | "receita_qsa" | "tse_doacoes_2022"
├── data_extracao     → Timestamp ISO
├── url_comprovante   → Link direto para PDF/API oficial
├── hash_registro     → SHA-256 do registro bruto
└── confianca         → "alta" | "media" | "baixa"
```

---

## 7. Camada 6 — API e Cache

### 7.1 FastAPI Endpoints

```python
# api/routes/modulos.py
from fastapi import APIRouter
router = APIRouter(prefix="/api/v1")

@router.get("/politico/{id}/rachadinha")
async def radar_rachadinha(id: str): ...

@router.get("/politico/{id}/fornecedores-suspeitos")
async def fornecedores_suspeitos(id: str): ...

@router.get("/politico/{id}/teletransporte")
async def teletransporte(id: str): ...

@router.get("/politico/{id}/emendas-ciclo")
async def emendas_ciclo(id: str): ...

@router.get("/politico/{id}/patrimonio")
async def patrimonio(id: str): ...

@router.get("/politico/{id}/dossie")
async def dossie(id: str): ...

@router.get("/ranking")
async def ranking(order_by: str = "custo_total", limit: int = 50): ...

@router.get("/grafo/{cnpj}")
async def grafo_empresa(cnpj: str, profundidade: int = 2): ...

@router.get("/diarios/suspeitos")
async def diarios_suspeitos(municipio: str = None, score_min: int = 50): ...
```

### 7.2 Redis Cache (Cache-Aside)

```python
# api/cache.py
import redis, json, hashlib
r = redis.Redis(host="localhost", port=6379, db=0)

def cache_aside(key_prefix: str, ttl: int = 3600):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{hashlib.md5(str(kwargs).encode()).hexdigest()}"
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            r.setex(cache_key, ttl, json.dumps(result, default=str))
            return result
        return wrapper
    return decorator
```

---

## 8. Camada 7 — Frontend e Visualização

### 8.1 Stack

| Componente | Tecnologia | Uso |
|---|---|---|
| Framework | React 19 + Vite | SPA mobile-first |
| Grafos | React-Flow ou vis-network | Módulo 6: Deep Proxy |
| Charts | Recharts ou Chart.js | Módulos 7, 8 |
| Timeline | react-chrono | Módulo 4/5: sequência temporal |
| Mapas | Leaflet / react-leaflet | Módulo 4: geolocalização |

### 8.2 Componentes por Módulo

```
src/components/
├── RadarRachadinha/
│   ├── RiskGauge.jsx             → Velocímetro 0-100
│   ├── DoadorCompulsorioTable.jsx
│   └── TriangulacaoAlert.jsx
├── FornecedoresSuspeitos/
│   ├── AnomalyScatterPlot.jsx    → Isolation Forest visualizado
│   └── HHIBar.jsx                → Concentração de gastos
├── ScannerDiarios/
│   ├── DispensasList.jsx
│   └── SuspeicaoScore.jsx        → Badge colorido 0-100
├── Teletransporte/
│   ├── MapConflict.jsx            → Mapa Brasília ↔ Estado
│   └── CalendarHeatmap.jsx
├── EmendasPix/
│   ├── CycleFlowDiagram.jsx      → Sankey: Dep→Prefeitura→Empresa→Doador
│   └── EmendaTimeline.jsx
├── DeepProxy/
│   ├── GraphCanvas.jsx            → React-Flow interativo
│   ├── NodeDetail.jsx
│   └── PathHighlight.jsx
├── Patrimonio/
│   ├── WealthChart.jsx            → Patrimônio por eleição
│   └── AnomalyBadge.jsx
├── Dossie/
│   ├── PoliticianCard.jsx
│   ├── RankingTable.jsx
│   └── CostBreakdown.jsx         → Pizza: salário vs CEAP
└── Rastreabilidade/
    ├── SourceTag.jsx              → "Receita Federal QSA"
    ├── AuditLink.jsx              → "Ver PDF original"
    └── ConfidenceBadge.jsx        → Alta/Média/Baixa
```

---

## 9. Orquestração e Scheduling

```cron
# /etc/cron.d/transparencia360

# CAIXA QUENTE (diário)
0 2 * * *   python -m extractors.camara_deputados
0 3 * * *   python -m extractors.portal_transparencia
0 4 * * *   python -m extractors.querido_diario
30 4 * * *  python -m extractors.pncp

# PROCESSAMENTO
0 5 * * *   python -m transforms.sanitize_all
0 6 * * *   python -m qa.run_expectations
0 7 * * *   python -m loaders.neo4j_incremental

# MOTORES DE ANÁLISE
0 8 * * *   python -m engines.run_all_modules

# CAIXA FRIA (mensal)
0 1 1 * *   python -m etl.receita_federal
0 1 15 * *  python -m etl.tse
```

**Observabilidade (OpenTelemetry):**

```python
# observability/tracing.py
from opentelemetry import trace
tracer = trace.get_tracer("transparencia360")

with tracer.start_as_current_span("etl.camara.extrair_despesas") as span:
    span.set_attribute("deputados.total", len(deputados))
    span.set_attribute("registros.extraidos", len(despesas))
```

---

## 10. Modelo de Dados Neo4j

```
(:Politico {id_camara, nome, partido, uf_origem, cargo, legislatura, salario_anual, fonte, data_extracao})
(:Pessoa {entity_id, nome, uf, cpf_hash, fonte, confianca})
(:Empresa {cnpj, razao_social, nome_fantasia, data_abertura, cnae, uf, situacao_cadastral, capital_social, fonte, hash_registro})
(:Despesa {id, valor, data, tipo, url_pdf, fonte, hash_registro})
(:Doacao {id, valor, data, tipo_fonte, ano_eleicao, fonte})
(:Emenda {id, valor, tipo, ano, municipio_destino_ibge, fonte})
(:Licitacao {id, objeto, valor_estimado, modalidade, data, municipio_ibge, fonte})
(:Municipio {ibge, nome, uf, populacao})
(:Sessao {id, data, tipo, local})
(:Sancao {id, tipo, data_inicio, data_fim, motivo, orgao_sancionador, fonte})
(:BemDeclarado {id, tipo, descricao, valor, ano_eleicao, fonte})
(:DiarioOficial {id, municipio_ibge, data, tipo_ato, excerto, score_suspeicao, cnpjs_extraidos, fonte})

// RELACIONAMENTOS
-[:GASTOU_CEAP {ano}]->
-[:PAGA_A]->
-[:TEM_SOCIO {qualificacao, data_entrada}]->
-[:DOOU_PARA {valor, data}]->
-[:AUTOR_EMENDA]->
-[:TRANSFERIU_PARA {valor, data}]->
-[:CONTRATOU {valor, modalidade}]->
-[:VENCEU_LICITACAO {valor_final}]->
-[:TEM_SANCAO]->
-[:DECLAROU_BEM]->
-[:PRESENTE_EM]->
-[:CITADA_EM {score}]->
-[:TEM_ASSESSOR {cargo, data_entrada, data_saida, salario}]->
-[:PARTE_EM {polo}]->
```

---

## 11. Mapeamento: Fonte → Módulo Consumidor

| Fonte | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Câmara CEAP** | ✅ | ✅ | — | ✅ | — | ✅ | — | ✅ | ✅ |
| **Senado CEAPS** | ✅ | ✅ | — | ✅ | — | ✅ | — | ✅ | ✅ |
| **CGU Servidores** | ✅ | — | — | — | — | — | — | ✅ | ✅ |
| **CGU Emendas** | — | — | — | — | ✅ | ✅ | — | ✅ | ✅ |
| **CGU CEIS/CNEP** | — | ✅ | — | — | — | ✅ | — | ✅ | ✅ |
| **TSE Doações** | ✅ | — | — | — | ✅ | ✅ | — | ✅ | ✅ |
| **TSE Bens** | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| **Receita QSA** | ✅ | ✅ | — | — | ✅ | ✅ | — | — | ✅ |
| **Querido Diário** | — | — | ✅ | — | ✅ | — | — | — | ✅ |
| **PNCP** | — | ✅ | — | — | ✅ | ✅ | — | — | ✅ |
| **TransfereGov** | — | — | — | — | ✅ | ✅ | — | ✅ | ✅ |
| **DataJud** | — | — | — | — | — | ✅ | — | ✅ | ✅ |
| **RAIS/CAGED** | ✅ | ✅ | — | — | — | — | — | — | ✅ |
| **CPGF** | — | — | — | ✅ | — | — | — | ✅ | ✅ |
| **Presenças** | — | — | — | ✅ | — | — | — | ✅ | ✅ |

---

## Estrutura de Diretórios

```
transparencia360/
├── extractors/              # Camada 1: Ingestão (Caixa Quente)
│   ├── camara_deputados.py
│   ├── senado.py
│   ├── portal_transparencia.py
│   ├── querido_diario.py
│   ├── pncp.py
│   └── transferegov.py
├── etl/                     # Camada 1: Dumps (Caixa Fria)
│   ├── receita_federal.py
│   ├── tse.py
│   └── rais.py
├── transforms/              # Camada 2: Sanitização
│   ├── sanitize.py
│   └── sanitize_all.py
├── qa/                      # Camada 2: Validação
│   ├── expectations.py
│   └── run_expectations.py
├── entity_resolution/       # Camada 3: Dedupe
│   ├── resolve_pessoas.py
│   └── ftm_schema.py
├── loaders/                 # Camada 4: Carga Neo4j
│   ├── neo4j_loader.py
│   ├── neo4j_incremental.py
│   └── bulk_import.sh
├── engines/                 # Camada 5: Os 9 Módulos
│   ├── modulo1_rachadinha.py
│   ├── modulo2_fornecedores.py
│   ├── modulo3_nlp_diarios.py
│   ├── modulo4_teletransporte.py
│   ├── modulo5_emendas_pix.py
│   ├── modulo6_deep_proxy.py
│   ├── modulo7_patrimonio.py
│   ├── modulo8_dossie.py
│   └── run_all_modules.py
├── queries/                 # Cypher isolados
│   ├── modulo1_rachadinha.cypher
│   ├── modulo4_teletransporte.cypher
│   ├── modulo5_emendas_pix.cypher
│   ├── modulo7_patrimonio.cypher
│   ├── modulo8_dossie.cypher
│   └── indexes.cypher
├── api/                     # Camada 6: FastAPI
│   ├── main.py
│   ├── routes/modulos.py
│   └── cache.py
├── frontend/src/components/ # Camada 7: React
├── observability/           # OpenTelemetry
├── data/
│   ├── raw/                 # Dados brutos
│   ├── clean/               # Sanitizados
│   └── ready/nodes/ + relationships/  # Parquets prontos
├── scripts/
│   ├── bulk_import.sh
│   └── parquet_to_neo4j_csv.py
└── docs/
    ├── ARQUITETURA_PIPELINE.md  ← ESTE DOCUMENTO
    ├── DATA_SOURCES.md
    └── ROADMAP.md
```

---

> **"O dinheiro público deixa rastro. Nosso trabalho é conectar os pontos."**
