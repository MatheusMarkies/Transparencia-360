"""
Portal da Transparência - Transactional Gatherer
API: https://api.portaldatransparencia.gov.br/swagger-ui.html
Requires: PORTAL_API_KEY env var

Endpoints used:
  - /servidores/remuneracao      → Folha de pagamento de servidores
  - /contratos                   → Contratos do Governo Federal
  - /licitacoes                  → Licitações públicas
  - /despesas/por-favorecido     → Despesas por CNPJ/CPF favorecido
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import logging
import json
from collections import defaultdict
from src.core.api_client import PortalTransparenciaClient, BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransparenciaGatherer:
    def __init__(self):
        self.api_key = os.getenv("PORTAL_API_KEY", "")
        self.client = PortalTransparenciaClient(api_key=self.api_key)
        self.backend = BackendClient()

    # ── Servidores (Folha de Pagamento) ──────────────────────────────
    def fetch_servidor_remuneracao(self, cpf: str, mes_ano: str) -> dict | None:
        """
        Busca a remuneração de um servidor federal por CPF.
        mes_ano format: 'YYYYMM' (ex: '202501')
        """
        return self.client.get("servidores/remuneracao", params={
            "cpf": cpf,
            "mesAno": mes_ano
        })

    def fetch_servidores_por_orgao(self, org_code: str, page: int = 1) -> list:
        """
        Lista servidores de um órgão específico.
        org_code: código do órgão (ex: '20000' para Presidência)
        """
        result = self.client.get("servidores", params={
            "codigoOrgaoServidorExercicio": org_code,
            "pagina": page
        })
        return result if result else []

    # ── Contratos Federais ──────────────────────────────────────────
    def fetch_contratos_por_cnpj(self, cnpj: str) -> list:
        """
        Busca contratos federais que envolvem um CNPJ fornecedor.
        Ideal para cruzar empresas suspeitas com licitações.
        """
        result = self.client.get("contratos", params={
            "cnpjContratada": cnpj
        })
        return result if result else []

    def fetch_contratos_por_orgao(self, org_code: str, page: int = 1) -> list:
        """
        Busca contratos de um órgão federal.
        """
        result = self.client.get("contratos", params={
            "codigoOrgao": org_code,
            "pagina": page
        })
        return result if result else []

    # ── Licitações ──────────────────────────────────────────────────
    def fetch_licitacoes_por_cnpj(self, cnpj: str) -> list:
        """
        Busca licitações vencidas por um CNPJ.
        Essencial para fechar o ciclo: O político facilita a licitação para a empresa do laranja.
        """
        result = self.client.get("licitacoes", params={
            "cnpjContratada": cnpj
        })
        return result if result else []

    # ── Despesas por Favorecido ─────────────────────────────────────
    def fetch_despesas_por_favorecido(self, cnpj_cpf: str, ano: int = 2025) -> list:
        """
        Verifica quanto dinheiro público um CNPJ/CPF recebeu diretamente.
        """
        result = self.client.get("despesas/por-favorecido", params={
            "codigoFavorecido": cnpj_cpf,
            "ano": ano
        })
        return result if result else []

    # ── Cross-reference engine ──────────────────────────────────────
    def cross_check_assessor_empresas(self, assessor_cpf: str, suspect_cnpjs: list[str]) -> dict:
        """
        Dado o CPF de um assessor parlamentar, verifica se alguma das empresas
        suspeitas (da Cota Parlamentar) tem contrato com o governo federal.
        
        Retorna um mapa de CNPJ -> valor total de contratos encontrados.
        """
        results = {}
        for cnpj in suspect_cnpjs:
            contratos = self.fetch_contratos_por_cnpj(cnpj)
            if contratos:
                total_valor = sum(
                    float(c.get("valorInicial", 0)) 
                    for c in contratos 
                    if isinstance(c, dict)
                )
                results[cnpj] = {
                    "total_contratos": len(contratos),
                    "valor_total": total_valor,
                    "contratos": contratos[:5]  # amostra dos 5 primeiros
                }
                logger.info(f"  🔍 CNPJ {cnpj}: {len(contratos)} contratos, R${total_valor:,.2f}")
        return results

    def run_salary_scan(self, cpf_list: list[str], mes_ano: str = "202501") -> list[dict]:
        """
        Escaneia uma lista de CPFs retornando as remunerações encontradas.
        Usado para validar se assessores recebem salário compatível.
        """
        scan_results = []
        for cpf in cpf_list:
            logger.info(f"  Buscando remuneração para CPF {cpf[:3]}...***")
            data = self.fetch_servidor_remuneracao(cpf, mes_ano)
            if data:
                scan_results.append({
                    "cpf": cpf,
                    "data": data
                })
        logger.info(f"  Scan concluído: {len(scan_results)}/{len(cpf_list)} CPFs encontrados.")
        return scan_results


# Backward-compatible top-level function
def fetch_servidor_remuneracao(cpf: str, mes_ano: str):
    gatherer = TransparenciaGatherer()
    return gatherer.fetch_servidor_remuneracao(cpf, mes_ano)


if __name__ == "__main__":
    gatherer = TransparenciaGatherer()
    # Example: scan contracts for a known suspicious CNPJ
    logger.info("=== Portal da Transparência - Gatherer ===")
    
    # Test with a dummy CNPJ
    contratos = gatherer.fetch_contratos_por_cnpj("00000000000191")  # Banco do Brasil (test)
    logger.info(f"Found {len(contratos) if contratos else 0} contracts")
