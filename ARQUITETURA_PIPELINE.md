# 🏗️ Arquitetura Completa do Pipeline de Dados — Transparência 360

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
└── (:
Empresa)-[:CITADA_EM]->(:DiarioOficial)
```
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
