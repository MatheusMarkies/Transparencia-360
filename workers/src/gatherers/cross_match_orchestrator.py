"""
Cross-Match Orchestrator — Neo4j Deep Proxy Network Builder

Este é o orquestrador principal que coordena TODOS os gatherers e loaders
para construir o grafo de 3º grau completo no Neo4j.

Pipeline:
  1. Câmara + Senado → Lista de políticos
  2. Rachadinha Worker → CNPJs suspeitos (CEAP) + CPFs de assessores
  3. Brasil API → QSA desses CNPJs → Nomes de sócios
  4. Receita Federal (Batch) → QSA completo de todas empresas BR
  5. TSE → Doações de campanha → Cruzar com sócios
  6. Portal da Transparência → Contratos federais dos CNPJs
  7. Querido Diário → Licitações locais
  8. DataJud → Processos judiciais contra envolvidos
  9. Neo4j → Construir o grafo e buscar caminhos longos

Caminho final buscado:
  Político → contratou → Empresa A ← sócio ← Pessoa X →
  sócio → Empresa B ← doou_para_campanha ← Pessoa Y →
  doou_para_campanha → Político
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import json
import logging
import time
from typing import Optional
from collections import defaultdict

# Internal modules
from src.core.api_client import GovAPIClient, BackendClient
from src.gatherers.transparencia_gatherer import TransparenciaGatherer
from src.gatherers.brasil_api_gatherer import BrasilAPIGatherer
from src.gatherers.querido_diario_gatherer import QueridoDiarioGatherer
from src.loaders.tse_batch_loader import TSEBatchLoader
from src.loaders.datajud_loader import DataJudLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"


class CrossMatchOrchestrator:
    """
    Orquestrador central que coordena todos os gatherers/loaders
    para construir redes de proxy de 3º grau no Neo4j.
    """

    def __init__(self, neo4j_session=None):
        self.neo4j = neo4j_session
        self.camara = GovAPIClient(CAMARA_API, request_delay=0.2)
        self.backend = BackendClient()
        self.transparencia = TransparenciaGatherer()
        self.brasil_api = BrasilAPIGatherer(request_delay=0.5)
        self.querido_diario = QueridoDiarioGatherer()
        self.tse = TSEBatchLoader()
        self.datajud = DataJudLoader()

        # Accumulated evidence
        self.evidence = defaultdict(lambda: {
            "cnpjs_suspeitos": [],
            "socios_encontrados": [],
            "contratos_federais": [],
            "mencoes_diario_oficial": [],
            "doacoes_campanha": [],
            "processos_judiciais": [],
            "risk_score": 0
        })

    # ── Step 1: Coleta de Deputados ─────────────────────────────────
    def step_1_fetch_deputies(self, limit: int = 50) -> list[dict]:
        """Busca lista de deputados da Câmara."""
        logger.info("═══ STEP 1: Buscando deputados da Câmara ═══")
        deputies = []
        page = 1
        while len(deputies) < limit:
            resp = self.camara.get("deputados", params={"pagina": page, "itens": 100})
            if not resp or "dados" not in resp:
                break
            deputies.extend(resp["dados"])
            if not any(l.get("rel") == "next" for l in resp.get("links", [])):
                break
            page += 1
        deputies = deputies[:limit]
        logger.info(f"  ✅ {len(deputies)} deputados encontrados")
        return deputies

    # ── Step 2: Extração de CNPJs Suspeitos (CEAP) ──────────────────
    def step_2_extract_suspect_cnpjs(self, dep_id: int) -> list[str]:
        """
        Analisa a Cota Parlamentar (CEAP) de um deputado procurando
        fornecedores com concentração atípica de pagamentos.
        Retorna lista de CNPJs suspeitos.
        """
        logger.info(f"  STEP 2: Analisando CEAP do deputado {dep_id}...")
        all_expenses = []
        page = 1
        while True:
            resp = self.camara.get(f"deputados/{dep_id}/despesas", params={
                "ano": 2025, "pagina": page, "itens": 100
            })
            if not resp or "dados" not in resp or len(resp["dados"]) == 0:
                break
            all_expenses.extend(resp["dados"])
            if not any(l.get("rel") == "next" for l in resp.get("links", [])):
                break
            page += 1

        # Aggregate by supplier CNPJ
        supplier_totals = defaultdict(float)
        supplier_names = {}
        for exp in all_expenses:
            cnpj = exp.get("cnpjCpfFornecedor", "")
            if cnpj and len(cnpj) >= 14:  # CNPJ only
                supplier_totals[cnpj] += float(exp.get("valorLiquido", 0))
                supplier_names[cnpj] = exp.get("nomeFornecedor", "")

        if not supplier_totals:
            return []

        # Flag CNPJs with > 30% concentration
        total_expenses = sum(supplier_totals.values())
        suspect_cnpjs = []
        for cnpj, total in supplier_totals.items():
            concentration = total / total_expenses if total_expenses > 0 else 0
            if concentration > 0.3 and total > 20000:
                suspect_cnpjs.append(cnpj)
                logger.info(f"    🚨 CNPJ suspeito: {supplier_names[cnpj]} ({cnpj}) "
                          f"- R${total:,.2f} ({concentration*100:.1f}%)")

        return suspect_cnpjs

    # ── Step 3: QSA Lookup via Brasil API ───────────────────────────
    def step_3_lookup_qsa(self, cnpj_list: list[str]) -> dict:
        """
        Para cada CNPJ suspeito, busca o QSA completo via Brasil API.
        Retorna {cnpj: {socios: [...], dados: {...}}}
        """
        logger.info(f"  STEP 3: Consultando QSA de {len(cnpj_list)} CNPJs via Brasil API...")
        results = {}
        for cnpj in cnpj_list:
            data = self.brasil_api.fetch_cnpj(cnpj)
            if data:
                socios = self.brasil_api.extract_qsa(data)
                results[cnpj] = {
                    "razao_social": data.get("razao_social", ""),
                    "socios": socios,
                    "atividade": data.get("cnae_fiscal_descricao", ""),
                    "municipio": data.get("municipio", ""),
                    "uf": data.get("uf", "")
                }
                for s in socios:
                    logger.info(f"    👤 Sócio: {s.get('nome_socio_pj', 'N/A')}")
        return results

    # ── Step 4: Contratos Federais (Portal da Transparência) ────────
    def step_4_check_federal_contracts(self, cnpj_list: list[str]) -> dict:
        """
        Verifica se os CNPJs suspeitos possuem contratos com o Governo Federal.
        """
        logger.info(f"  STEP 4: Verificando contratos federais para {len(cnpj_list)} CNPJs...")
        return self.transparencia.cross_check_assessor_empresas("", cnpj_list)

    # ── Step 5: Menções em Diários Oficiais (OKBR) ──────────────────
    def step_5_check_official_gazettes(self, cnpj_list: list[str], names: list[str]) -> list[dict]:
        """
        Busca menções de CNPJs e nomes suspeitos em Diários Oficiais municipais.
        """
        logger.info(f"  STEP 5: Buscando em Diários Oficiais ({len(cnpj_list)} CNPJs, {len(names)} nomes)...")
        all_mentions = []
        for cnpj in cnpj_list[:5]:  # Limit to avoid rate limits
            result = self.querido_diario.cross_check_suspect(cnpj, names[:3])
            all_mentions.append(result)
        return all_mentions

    # ── Step 6: Processos Judiciais (DataJud) ───────────────────────
    def step_6_check_judicial_records(self, names: list[str]) -> list[dict]:
        """
        Verifica se sócios/assessores possuem processos de improbidade.
        """
        logger.info(f"  STEP 6: Verificando antecedentes judiciais de {len(names)} pessoas...")
        records = []
        for name in names[:5]:  # Limit
            result = self.datajud.build_judicial_risk_score(name)
            if result["risk_score"] > 0:
                records.append(result)
        return records

    # ── Step 7: Ingestão no Neo4j ───────────────────────────────────
    def step_7_ingest_to_neo4j(self, politician: dict, qsa_data: dict, donations: list = None):
        """
        Monta o grafo completo no Neo4j para um político específico.
        """
        if not self.neo4j:
            logger.warning("  ⚠️ Neo4j session não disponível. Pulando ingestão.")
            return

        logger.info(f"  STEP 7: Ingerindo grafo neo4j para {politician.get('nome', 'N/A')}...")
        dep_id = str(politician.get("id", ""))

        # Create Politiker node
        self.neo4j.run("""
            MERGE (p:Politico {id: $id})
            SET p.name = $name, p.party = $party, p.state = $state
        """, id=dep_id, name=politician.get("nome", ""),
           party=politician.get("siglaPartido", ""),
           state=politician.get("siglaUf", ""))

        # Add empresas and sócios
        for cnpj, info in qsa_data.items():
            # Empresa node + CONTRATOU relationship
            self.neo4j.run("""
                MATCH (p:Politico {id: $pol_id})
                MERGE (e:Empresa {cnpj: $cnpj})
                SET e.name = $name, e.atividade = $atividade
                MERGE (p)-[:CONTRATOU]->(e)
            """, pol_id=dep_id, cnpj=cnpj,
               name=info["razao_social"], atividade=info.get("atividade", ""))

            # Sócios
            for socio in info.get("socios", []):
                nome_socio = socio.get("nome_socio_pj", "UNKNOWN")
                cpf_cnpj_socio = socio.get("cnpj_cpf_do_socio", "")
                self.neo4j.run("""
                    MATCH (e:Empresa {cnpj: $cnpj})
                    MERGE (pe:Pessoa {name: $name})
                    ON CREATE SET pe.cpf = $cpf
                    MERGE (pe)-[:SOCIO_ADMINISTRADOR_DE]->(e)
                """, cnpj=cnpj, name=nome_socio, cpf=cpf_cnpj_socio)

        # Add campaign donations if available
        if donations:
            for d in donations:
                self.neo4j.run("""
                    MATCH (p:Politico {id: $pol_id})
                    MERGE (doador:Pessoa {name: $doador_name})
                    ON CREATE SET doador.cpf = $doador_cpf
                    MERGE (doador)-[:DOOU_PARA_CAMPANHA {valor: $valor}]->(p)
                """, pol_id=dep_id, doador_name=d.get("nome_doador", ""),
                   doador_cpf=d.get("cpf", ""), valor=d.get("valor_doado", 0))

    # ── Master Pipeline ─────────────────────────────────────────────
    def run(self, limit: int = 10):
        """
        Executa o pipeline completo de cross-matching para detectar
        redes de proxy de 3º grau.
        """
        logger.info("╔════════════════════════════════════════════════════╗")
        logger.info("║  CROSS-MATCH ORCHESTRATOR — Deep Proxy Detection  ║")
        logger.info("╚════════════════════════════════════════════════════╝")
        start = time.time()

        # Step 1: Get deputies
        deputies = self.step_1_fetch_deputies(limit=limit)

        for dep in deputies:
            dep_id = dep["id"]
            dep_name = dep["nome"]
            logger.info(f"\n{'='*60}")
            logger.info(f"  📋 Analisando: {dep_name} ({dep.get('siglaPartido')}-{dep.get('siglaUf')})")
            logger.info(f"{'='*60}")

            # Step 2: Extract suspect CNPJs from CEAP
            suspect_cnpjs = self.step_2_extract_suspect_cnpjs(dep_id)
            if not suspect_cnpjs:
                logger.info(f"  ✅ Sem CNPJs suspeitos. Próximo deputado.")
                continue

            # Step 3: Lookup QSA
            qsa_data = self.step_3_lookup_qsa(suspect_cnpjs)

            # Collect sócio names for further checks
            all_socio_names = []
            for cnpj_info in qsa_data.values():
                for s in cnpj_info.get("socios", []):
                    all_socio_names.append(s.get("nome_socio_pj", ""))

            # Step 4: Federal contracts
            contracts = self.step_4_check_federal_contracts(suspect_cnpjs)

            # Step 5: Official gazettes
            gazette_mentions = self.step_5_check_official_gazettes(suspect_cnpjs, all_socio_names)

            # Step 6: Judicial records
            judicial_records = self.step_6_check_judicial_records(all_socio_names)

            # Step 7: Neo4j ingestion
            self.step_7_ingest_to_neo4j(dep, qsa_data)

            # Accumulate evidence
            self.evidence[dep_name]["cnpjs_suspeitos"] = suspect_cnpjs
            self.evidence[dep_name]["socios_encontrados"] = all_socio_names
            self.evidence[dep_name]["contratos_federais"] = contracts
            self.evidence[dep_name]["mencoes_diario_oficial"] = gazette_mentions
            self.evidence[dep_name]["processos_judiciais"] = judicial_records

            # Compute composite risk
            risk = 0
            risk += min(30, len(suspect_cnpjs) * 10)
            risk += min(20, len(contracts) * 5)
            risk += min(20, sum(1 for g in gazette_mentions if g.get("cnpj_total_mentions", 0) > 0) * 10)
            risk += min(30, sum(r.get("risk_score", 0) for r in judicial_records))
            self.evidence[dep_name]["risk_score"] = min(100, risk)

            logger.info(f"\n  🎯 RISK SCORE COMPOSTO: {self.evidence[dep_name]['risk_score']}/100")

        elapsed = time.time() - start
        logger.info(f"\n{'='*60}")
        logger.info(f"  Pipeline concluído em {elapsed:.1f}s")
        logger.info(f"  {len(self.evidence)} deputados analisados")
        logger.info(f"{'='*60}")

        # Report top risks
        sorted_risks = sorted(self.evidence.items(), key=lambda x: x[1]["risk_score"], reverse=True)
        logger.info("\n  🏆 TOP 5 RISCOS:")
        for name, data in sorted_risks[:5]:
            logger.info(f"    {data['risk_score']}/100 - {name}")

        return dict(self.evidence)


if __name__ == "__main__":
    orchestrator = CrossMatchOrchestrator()
    # Run for 10 deputies (without Neo4j session for dry-run)
    results = orchestrator.run(limit=10)
    
    # Save results
    output_path = "/tmp/cross_match_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"  Resultados salvos em: {output_path}")
