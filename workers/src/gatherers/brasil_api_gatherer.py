"""
Brasil API - CNPJ Gatherer (Transactional / Real-Time)
API: https://brasilapi.com.br/api/cnpj/v1/{cnpj}

Consulta pontual e rápida de dados cadastrais de um CNPJ suspeito
identificado pelo motor de scoring. Retorna Razão Social, QSA (Quadro
de Sócios e Administradores), atividades e endereço.

Não exige API Key.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import logging
import time
import requests
from typing import Optional, Any
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BRASIL_API_BASE = "https://brasilapi.com.br/api/cnpj/v1"


class BrasilAPIGatherer:
    """
    Consulta pontual de CNPJs suspeitos via BrasilAPI.
    Foco: extrair o QSA (Quadro de Sócios e Administradores).
    """
    def __init__(self, request_delay: float = 0.5):
        self.base_url = BRASIL_API_BASE
        self.request_delay = request_delay
        self.backend = BackendClient()

    def fetch_cnpj(self, cnpj: str) -> Optional[dict]:
        """
        Busca dados completos de um CNPJ. Retorna dict com:
        - razao_social, nome_fantasia
        - cnae_fiscal, cnae_fiscal_descricao
        - qsa: [{nome_socio_pj, cnpj_cpf_do_socio, ...}]
        - logradouro, municipio, uf
        """
        # Clean CNPJ: remove dots, slashes, dashes
        cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
        url = f"{self.base_url}/{cnpj_clean}"

        try:
            time.sleep(self.request_delay)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            logger.info(f"  ✅ CNPJ {cnpj_clean}: {data.get('razao_social', 'N/A')}")
            return data
        except requests.RequestException as e:
            logger.warning(f"  ❌ Falha ao consultar CNPJ {cnpj_clean}: {e}")
            return None

    def extract_qsa(self, cnpj_data: dict) -> list[dict]:
        """
        Extrai o Quadro de Sócios e Administradores (QSA) do resultado
        da consulta CNPJ.
        """
        if not cnpj_data:
            return []
        return cnpj_data.get("qsa", [])

    def batch_lookup(self, cnpj_list: list[str]) -> dict[str, dict]:
        """
        Consulta múltiplos CNPJs em sequência respeitando rate limit.
        Retorna {cnpj: {dados_completos}} para cada CNPJ encontrado.
        """
        results = {}
        total = len(cnpj_list)
        for idx, cnpj in enumerate(cnpj_list):
            logger.info(f"  [{idx+1}/{total}] Consultando CNPJ {cnpj}...")
            data = self.fetch_cnpj(cnpj)
            if data:
                results[cnpj] = data
        logger.info(f"  Batch lookup concluído: {len(results)}/{total} CNPJs encontrados.")
        return results

    def map_socios_to_graph(self, cnpj_data: dict) -> list[dict]:
        """
        Converte o QSA em nós e edges prontos para ingestão no Neo4j.
        
        Retorna lista de dicts no formato:
        [
            {"tipo": "Empresa", "cnpj": "...", "nome": "..."},
            {"tipo": "Pessoa", "nome": "...", "cpf_cnpj": "...", "qualificacao": "..."},
            {"tipo": "rel", "de": "...", "para": "...", "tipo_rel": "SOCIO_DE"}
        ]
        """
        if not cnpj_data:
            return []

        nodes_edges = []
        cnpj = cnpj_data.get("cnpj", "")
        nome_empresa = cnpj_data.get("razao_social", "DESCONHECIDA")

        # Empresa node
        nodes_edges.append({
            "tipo": "Empresa",
            "cnpj": cnpj,
            "nome": nome_empresa,
            "atividade": cnpj_data.get("cnae_fiscal_descricao", ""),
            "municipio": cnpj_data.get("municipio", ""),
            "uf": cnpj_data.get("uf", "")
        })

        # Sócios/Administradores
        for socio in cnpj_data.get("qsa", []):
            nome_socio = socio.get("nome_socio_pj", "DESCONHECIDO")
            cpf_cnpj = socio.get("cnpj_cpf_do_socio", "")
            qualificacao = socio.get("codigo_qualificacao_socio", "")

            nodes_edges.append({
                "tipo": "Pessoa",
                "nome": nome_socio,
                "cpf_cnpj": cpf_cnpj,
                "qualificacao": qualificacao
            })
            nodes_edges.append({
                "tipo": "rel",
                "de": nome_socio,
                "para": cnpj,
                "tipo_rel": "SOCIO_ADMINISTRADOR_DE"
            })

        return nodes_edges


if __name__ == "__main__":
    gatherer = BrasilAPIGatherer()
    logger.info("=== Brasil API - CNPJ Gatherer ===")

    # Test with Banco do Brasil S.A.
    test_cnpj = "00000000000191"
    data = gatherer.fetch_cnpj(test_cnpj)
    if data:
        socios = gatherer.extract_qsa(data)
        logger.info(f"  QSA: {len(socios)} sócios/administradores encontrados")
        for s in socios[:5]:
            logger.info(f"    → {s.get('nome_socio_pj', 'N/A')}")
