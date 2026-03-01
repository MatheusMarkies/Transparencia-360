"""
Gazette Text Fetcher
━━━━━━━━━━━━━━━━━━━
Baixa o texto completo de Diários Oficiais via Querido Diário API
e orquestra a extração NLP em lote.

Pipeline:
  1. Busca diários por CNPJ/nome de empresa suspeita 
  2. Para cada match, baixa o texto completo (excerto ou TXT)
  3. Passa cada texto pelo GazetteNLPExtractor
  4. Acumula os resultados estruturados para ingestão no Neo4j
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import logging
import time
import requests
from typing import Optional
from src.gatherers.querido_diario_gatherer import QueridoDiarioGatherer
from src.nlp.gazette_nlp_extractor import GazetteNLPExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUERIDO_DIARIO_API = "https://api.queridodiario.ok.org.br"


class GazetteTextFetcher:
    """
    Orquestra a busca e download de textos de Diários Oficiais
    usando a API do Querido Diário + pipeline NLP.
    """

    def __init__(self, request_delay: float = 1.0):
        self.gatherer = QueridoDiarioGatherer(request_delay=request_delay)
        self.extractor = GazetteNLPExtractor()
        self.request_delay = request_delay

    def fetch_gazette_text(self, gazette_id: str) -> Optional[str]:
        """
        Baixa o texto completo de um diário pelo ID.
        Tenta primeiro o endpoint de texto, depois o endpoint de excertos.
        """
        # Querido Diário exposes txt_url in gazette objects
        url = f"{QUERIDO_DIARIO_API}/gazettes/{gazette_id}"
        try:
            time.sleep(self.request_delay)
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            # Try txt_url first (full text)
            txt_url = data.get("txt_url", "")
            if txt_url:
                time.sleep(self.request_delay)
                txt_resp = requests.get(txt_url, timeout=60)
                txt_resp.raise_for_status()
                return txt_resp.text
            
            # Fallback to excerpts
            excerpts = data.get("excerpts", [])
            if excerpts:
                return "\n\n".join(excerpts)
            
            return None
        except requests.RequestException as e:
            logger.warning(f"  ❌ Falha ao baixar texto do diário {gazette_id}: {e}")
            return None

    def search_and_extract(
        self,
        query: str,
        since: str = "2020-01-01",
        max_results: int = 50,
        territory_id: Optional[str] = None
    ) -> list[dict]:
        """
        Pipeline completo:
        1. Busca diários com o query (CNPJ, nome, etc.)
        2. Pega o excerto de cada match
        3. Roda NLP em cada excerto
        4. Retorna lista de resultados NLP
        """
        logger.info(f"  📰 Buscando diários para '{query}'...")
        all_results = []
        offset = 0
        page_size = 20

        while len(all_results) < max_results:
            data = self.gatherer.search_gazettes(
                query=query,
                since=since,
                size=page_size,
                offset=offset,
                territory_id=territory_id
            )
            
            gazettes = data.get("gazettes", [])
            if not gazettes:
                break
            
            for g in gazettes:
                if len(all_results) >= max_results:
                    break
                
                gazette_id = g.get("territory_id", "") + "_" + g.get("date", "")
                territory = g.get("territory_name", "N/A")
                date = g.get("date", "")
                url = g.get("url", "")
                excerpts = g.get("excerpts", [])
                
                # Use excerpts as text (faster than downloading full gazette)
                text = "\n\n".join(excerpts) if excerpts else ""
                
                if not text or len(text) < 50:
                    continue
                
                # Run NLP extraction
                nlp_result = self.extractor.extract_all(
                    raw_text=text,
                    source_url=url,
                    territory=territory,
                    date=date
                )
                
                # Only keep results with actual entities
                entity_count = sum(
                    len(v) for v in nlp_result["entities"].values() 
                    if isinstance(v, list)
                )
                if entity_count > 0:
                    nlp_result["gazette_territory"] = territory
                    nlp_result["gazette_date"] = date
                    nlp_result["gazette_url"] = url
                    all_results.append(nlp_result)
            
            offset += page_size
            total = data.get("total_gazettes", 0)
            if offset >= total:
                break

        logger.info(f"  ✅ {len(all_results)} diários processados com entidades extraídas")
        return all_results

    def scan_suspect_cnpjs(
        self,
        cnpj_list: list[str],
        since: str = "2020-01-01"
    ) -> dict[str, list[dict]]:
        """
        Para cada CNPJ suspeito, busca menções em Diários Oficiais
        e extrai entidades NLP.
        """
        logger.info(f"  🔍 Escaneando {len(cnpj_list)} CNPJs em Diários Oficiais...")
        results = {}
        
        for cnpj in cnpj_list:
            cnpj_results = self.search_and_extract(
                query=cnpj,
                since=since,
                max_results=20
            )
            if cnpj_results:
                results[cnpj] = cnpj_results
                
                # Summarize findings
                total_dispensas = sum(
                    len([m for m in r["entities"]["modalidades"] if m.get("is_dispensa")])
                    for r in cnpj_results
                )
                total_valor = sum(
                    sum(v["valor_float"] for v in r["entities"]["valores"])
                    for r in cnpj_results
                )
                max_score = max(r["suspicion_score"] for r in cnpj_results)
                
                logger.info(
                    f"    CNPJ {cnpj}: {len(cnpj_results)} diários, "
                    f"{total_dispensas} dispensas, "
                    f"R$ {total_valor:,.2f} total, "
                    f"max score {max_score}/100"
                )
        
        return results

    def scan_politician_network(
        self,
        politician_name: str,
        cnpj_list: list[str],
        associate_names: list[str],
        since: str = "2020-01-01"
    ) -> dict:
        """
        Pipeline completo para um político:
        1. Busca menções do nome do político
        2. Busca CNPJs suspeitos
        3. Busca nomes de associados (assessores, sócios)
        4. Cruza padrões entre todas as fontes
        """
        logger.info(f"\n  {'='*50}")
        logger.info(f"  📰 GAZETTE SCAN: {politician_name}")
        logger.info(f"  {'='*50}")
        
        # 1. Politician mentions
        politician_results = self.search_and_extract(
            query=f'"{politician_name}"',
            since=since,
            max_results=10
        )
        
        # 2. CNPJ mentions
        cnpj_results = self.scan_suspect_cnpjs(cnpj_list, since)
        
        # 3. Associate mentions
        associate_results = {}
        for name in associate_names[:5]:  # Limit to avoid rate limits
            assoc_data = self.search_and_extract(
                query=f'"{name}"',
                since=since,
                max_results=5
            )
            if assoc_data:
                associate_results[name] = assoc_data
        
        # 4. Cross-reference
        cross_findings = self._cross_reference(
            politician_name, politician_results,
            cnpj_results, associate_results
        )
        
        return {
            "politician": politician_name,
            "politician_gazette_mentions": len(politician_results),
            "cnpj_scan_results": {k: len(v) for k, v in cnpj_results.items()},
            "associate_mentions": {k: len(v) for k, v in associate_results.items()},
            "cross_findings": cross_findings,
            "total_dispensas_found": sum(
                sum(
                    len([m for m in r["entities"]["modalidades"] if m.get("is_dispensa")])
                    for r in results
                )
                for results in cnpj_results.values()
            ),
            "max_suspicion_score": max(
                (r["suspicion_score"] for results in cnpj_results.values() for r in results),
                default=0
            ),
            "details": {
                "politician": politician_results[:5],
                "cnpjs": {k: v[:3] for k, v in cnpj_results.items()},
                "associates": {k: v[:3] for k, v in associate_results.items()}
            }
        }

    def _cross_reference(self, politician_name, pol_results, 
                         cnpj_results, associate_results) -> list[dict]:
        """
        Cruza dados entre político, CNPJs e associados para encontrar
        padrões de conluio em licitações.
        """
        findings = []
        
        # Pattern: Same CNPJ appears in multiple dispensas
        for cnpj, results in cnpj_results.items():
            dispensa_count = sum(
                len([m for m in r["entities"]["modalidades"] if m.get("is_dispensa")])
                for r in results
            )
            if dispensa_count >= 2:
                findings.append({
                    "type": "DISPENSAS_REPETIDAS",
                    "severity": "CRITICAL",
                    "cnpj": cnpj,
                    "count": dispensa_count,
                    "detail": f"CNPJ {cnpj} aparece em {dispensa_count} dispensas de licitação"
                })
        
        # Pattern: Associate name appears with CNPJ in same gazette
        for name, assoc_results in associate_results.items():
            for ar in assoc_results:
                cnpjs_in_gazette = [c["cnpj"] for c in ar["entities"]["cnpjs"]]
                for cnpj in cnpj_results:
                    clean_cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
                    for gc in cnpjs_in_gazette:
                        clean_gc = gc.replace(".", "").replace("/", "").replace("-", "")
                        if clean_cnpj == clean_gc:
                            findings.append({
                                "type": "ASSOCIADO_COM_CNPJ_SUSPEITO",
                                "severity": "HIGH",
                                "associate": name,
                                "cnpj": cnpj,
                                "gazette_date": ar.get("gazette_date", ""),
                                "detail": f"Associado '{name}' mencionado com CNPJ {cnpj} em diário oficial"
                            })
        
        return findings


if __name__ == "__main__":
    fetcher = GazetteTextFetcher()
    logger.info("=== Gazette Text Fetcher + NLP Pipeline ===")
    
    # Test: search for dispensas de licitação
    results = fetcher.search_and_extract(
        query="dispensa de licitação",
        since="2025-01-01",
        max_results=5
    )
    
    for r in results:
        logger.info(f"\n  📄 {r.get('gazette_territory')} ({r.get('gazette_date')})")
        logger.info(f"     Score: {r['suspicion_score']}/100")
        logger.info(f"     CNPJs: {len(r['entities']['cnpjs'])}")
        logger.info(f"     Valores: {len(r['entities']['valores'])}")
        logger.info(f"     Patterns: {len(r['suspicious_patterns'])}")
