"""
Querido Diário - OKBR Gatherer (Transactional / Real-Time)
API: https://queridodiario.ok.org.br/api/docs

Busca menções a CNPJs ou nomes em Diários Oficiais de municípios brasileiros.
Foco: detectar licitações e contratos locais que referenciem CNPJs
ou nomes de assessores identificados como suspeitos pelo scoring engine.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import logging
import time
import requests
from typing import Optional
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUERIDO_DIARIO_BASE = "https://api.queridodiario.ok.org.br/gazettes"


class QueridoDiarioGatherer:
    """
    Busca menções em Diários Oficiais de municípios (OKBR).
    Ideal para rastrear contratos locais envolvendo CNPJs ou
    nomes de assessores suspeitos.
    """
    def __init__(self, request_delay: float = 1.0):
        self.base_url = QUERIDO_DIARIO_BASE
        self.request_delay = request_delay
        self.backend = BackendClient()

    def search_gazettes(
        self,
        query: str,
        territory_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        size: int = 10,
        offset: int = 0
    ) -> dict:
        """
        Busca diários oficiais por texto livre (CNPJ, nome, etc.)
        
        Args:
            query: texto livre (ex: "12.345.678/0001-00" ou "João Silva")
            territory_id: código IBGE do município (ex: "3550308" para SP capital)
            since: data início (YYYY-MM-DD)
            until: data fim (YYYY-MM-DD)
            size: resultados por página
            offset: paginação
            
        Returns:
            dict com { total_gazettes, gazettes: [...] }
        """
        params = {
            "querystring": query,
            "size": size,
            "offset": offset
        }
        if territory_id:
            params["territory_ids"] = territory_id
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        try:
            time.sleep(self.request_delay)
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            total = data.get("total_gazettes", 0)
            logger.info(f"  📰 Query '{query[:30]}...': {total} menções em Diários Oficiais")
            return data
        except requests.RequestException as e:
            logger.warning(f"  ❌ Falha ao buscar no Querido Diário: {e}")
            return {"total_gazettes": 0, "gazettes": []}

    def search_cnpj_mentions(self, cnpj: str, since: str = "2020-01-01") -> list[dict]:
        """
        Busca todas as menções de um CNPJ nos Diários Oficiais 
        desde uma data base.
        """
        results = []
        offset = 0
        page_size = 20
        
        while True:
            data = self.search_gazettes(
                query=cnpj,
                since=since,
                size=page_size,
                offset=offset
            )
            gazettes = data.get("gazettes", [])
            if not gazettes:
                break
            
            for g in gazettes:
                results.append({
                    "territory_name": g.get("territory_name", "N/A"),
                    "territory_id": g.get("territory_id", ""),
                    "date": g.get("date", ""),
                    "scraped_at": g.get("scraped_at", ""),
                    "url": g.get("url", ""),
                    "excerpt": g.get("excerpts", [""])[0][:500] if g.get("excerpts") else "",
                    "state_code": g.get("state_code", "")
                })
            
            offset += page_size
            if offset >= data.get("total_gazettes", 0):
                break
        
        return results

    def search_person_mentions(self, name: str, territory_id: Optional[str] = None) -> list[dict]:
        """
        Busca menções de uma pessoa (assessor, sócio) em
        Diários Oficiais. Pode filtrar por município (territory_id).
        """
        data = self.search_gazettes(
            query=f'"{name}"',  # aspas para busca exata
            territory_id=territory_id,
            size=20
        )
        
        results = []
        for g in data.get("gazettes", []):
            results.append({
                "territory_name": g.get("territory_name", "N/A"),
                "date": g.get("date", ""),
                "url": g.get("url", ""),
                "excerpt": g.get("excerpts", [""])[0][:500] if g.get("excerpts") else ""
            })
        return results

    def cross_check_suspect(self, cnpj: str, names: list[str]) -> dict:
        """
        Para um CNPJ suspeito e uma lista de nomes relacionados,
        busca menções nos Diários Oficiais para encontrar evidências
        de contratos locais.
        """
        logger.info(f"  🔍 Cross-checking CNPJ {cnpj} e {len(names)} nomes...")
        
        cnpj_mentions = self.search_cnpj_mentions(cnpj)
        name_mentions = {}
        for name in names:
            mentions = self.search_person_mentions(name)
            if mentions:
                name_mentions[name] = mentions

        return {
            "cnpj": cnpj,
            "cnpj_total_mentions": len(cnpj_mentions),
            "cnpj_mentions": cnpj_mentions[:10],  # top 10
            "name_mentions": name_mentions
        }


if __name__ == "__main__":
    gatherer = QueridoDiarioGatherer()
    logger.info("=== Querido Diário - OKBR Gatherer ===")
    
    # Test: search for any CNPJ in recent gazettes
    test_results = gatherer.search_gazettes("licitação", size=3)
    for g in test_results.get("gazettes", []):
        logger.info(f"  📄 {g.get('territory_name')} - {g.get('date')}")
