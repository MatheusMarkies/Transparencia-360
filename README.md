# Transparência 360 - Auditoria Pública Inteligente

Plataforma de auditoria e monitoramento de dados públicos brasileiros, focada em detecção de anomalias (Funcionários Fantasmas, Rachadinha, Incoerência de Voto) e visualização de redes de influência.

## 🚀 Arquitetura do Sistema

O projeto é dividido em três camadas principais:

### 1. Backend (Spring Boot + Neo4j + PostgreSQL)
- **Tecnologias**: Java 17+, Spring Boot, Hibernate, Neo4j (Grafos), PostgreSQL (Relacional).
- **Função**: API REST para o frontend e motor de ingestão de grafos para análise de 2º e 3º grau de parentesco/sociedade.
- **Porta**: `8080`

### 2. Frontend (Vite + React + TailwindCSS)
- **Tecnologias**: React, TypeScript, Vis-Network/React-Flow (Grafos), Tailwind.
- **Função**: Dashboard interativo para visualização de riscos, evolução patrimonial e radares de probabilidade.
- **Porta**: `5173`

### 3. Workers de Extração (Python 3.10+)
- **Tecnologias**: `aiohttp`, `BeautifulSoup`, `scikit-learn` (ML), `RegEx` (NLP).
- **Função**: Pipeline de 17 etapas que consome APIs reais (Câmara, Portal da Transparência, TSE, DataJud, Querido Diário).
- **Caminho**: `workers/run_all_extractions.py`

---

## 🛠️ Como Executar Localmente

### Pré-requisitos
- Docker & Docker Compose
- Java 17
- Node.js 18+
- Python 3.10+

### Passo 1: Infraestrutura (Bancos de Dados)
Suba os containers do PostgreSQL e Neo4j:
```bash
docker-compose up -d
```
- **Neo4j UI**: [http://localhost:7474](http://localhost:7474) (Login: `neo4j/admin123`)
- **Postgres**: Porta `5432`

### Passo 2: Executar o Backend
```bash
cd backend
./gradlew bootRun
```

### Passo 3: Executar o Frontend
```bash
cd frontend
npm install
npm run dev
```

### Passo 4: Rodar o Pipeline de Extração (Python)
Pegue sua API Key no Portal da Transparência: https://portaldatransparencia.gov.br/api-de-dados
Certifique-se de configurar sua chave do Portal da Transparência:
```powershell
# Windows PowerShell
$env:PORTAL_API_KEY = "##########################"
```
Instale as dependências:
```bash
cd workers
pip install -r requirements.txt
```
Execute o pipeline completo:
```bash
python run_all_extractions.py --limit 10
```
Nesse comando fazemos a busca por 10 deputados, para a lista completa utilize 513.

---

## 🔍 O que o Pipeline v2.0 faz?

O script `run_all_extractions.py` executa 17 passos automáticos:
1.  **Gabinete Scraper**: Raspa a lista real de funcionários do site da Câmara.
2.  **Cross-Match**: Compara assessores com fornecedores de campanha e CEAP.
3.  **TSE Assets**: Baixa e cruza a evolução patrimonial real dos candidatos.
4.  **Gazette NLP**: Busca 'Dispensas de Licitação' em Diários Oficiais via Querido Diário.
5.  **DataJud**: Verifica processos de improbidade administrativa no CNJ.
6.  **Coerência NLP**: Compara o texto dos projetos de lei com os votos reais do parlamentar.
7.  **Emendas Pix**: Rastreia o fluxo circular de dinheiro em transferências especiais.

## 📁 Estrutura de Pastas
- `/backend`: API Spring Boot.
- `/frontend`: Dashboard React.
- `/workers`: Scripts de extração e análise Python.
- `/data/downloads`: Armazenamento local de transcrições e documentos auditados.

---
**Aviso**: Este sistema utiliza apenas APIs Públicas e Dados Abertos (Lei de Acesso à Informação).
