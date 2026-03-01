"""
DataJud - CNJ (Batch Loader / API)
Source: https://www.cnj.jus.br/programas-e-acoes/datajud/

Metadados do Judiciário brasileiro para cruzar CPFs de assessores
e empresas com histórico de processos por improbidade administrativa,
fraude em licitações, lavagem de dinheiro, etc.

Utiliza a API pública do DataJud (Elasticsearch-based) para buscar
processos judiciais por parte envolvida.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import os
import csv
import logging
import time
import requests
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DataJud public API endpoint
DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br/api_publica_"
DATAJUD_TRIBUNAIS = {
    "trf1": "trf1",   # Tribunal Regional Federal 1ª Região
    "trf2": "trf2",
    "trf3": "trf3",
    "trf4": "trf4",
    "trf5": "trf5",
    "stj": "stj",     # Superior Tribunal de Justiça
    "tst": "tst",     # Tribunal Superior do Trabalho
}

# Classes processuais relevantes para corrupção
CLASSES_IMPROBIDADE = [
    "Ação Civil Pública",
    "Ação de Improbidade Administrativa",
    "Inquérito Policial",
    "Ação Penal",
    "Mandado de Segurança",
]

# Assuntos (subjects) relevantes
ASSUNTOS_CORRUPTION = [
    "Improbidade Administrativa",
    "Crimes contra a Administração Pública",
    "Corrupção Passiva",
    "Corrupção Ativa",
    "Peculato",
    "Lavagem ou Ocultação de Bens",
    "Fraude em Licitações e Contratos Administrativos",
    "Enriquecimento Ilícito",
]


DATAJUD_PUBLIC_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="


class DataJudLoader:
    """
    Consulta o DataJud (CNJ) para encontrar processos judiciais
    envolvendo pessoas ou empresas suspeitas identificadas pelo motor.
    """
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("DATAJUD_API_KEY", DATAJUD_PUBLIC_KEY)
        self.headers = {
            "Authorization": f"APIKey {self.api_key}",
            "Content-Type": "application/json"
        }

    def search_processes(
        self,
        tribunal: str,
        query: str,
        size: int = 10
    ) -> list[dict]:
        """
        Busca processos em um tribunal específico pela API Elasticsearch.
        
        Args:
            tribunal: sigla do tribunal (trf1, stj, stf, etc.)
            query: nome da parte, CPF/CNPJ, ou número do processo
            size: resultados por página
        """
        url = f"{DATAJUD_BASE}{tribunal}/_search"
        
        body = {
            "size": size,
            "query": {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "dadosBasicos.polo.parte.pessoa.nome": {
                                    "query": query,
                                    "fuzziness": "AUTO",
                                    "operator": "and"
                                }
                            }
                        },
                        {
                            "match_phrase": {
                                "dadosBasicos.polo.parte.pessoa.nome": query
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "_source": [
                "numeroProcesso",
                "classe.nome",
                "assunto.nome",
                "dataAjuizamento", 
                "tribunal",
                "grau",
                "dadosBasicos.polo"
            ]
        }

        try:
            time.sleep(1.0)  # Respect rate limits
            response = requests.post(url, json=body, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            logger.info(f"  ⚖️ Tribunal {tribunal.upper()}: {len(hits)} processos encontrados para '{query}'")
            return [h.get("_source", {}) for h in hits]
        except requests.RequestException as e:
            logger.warning(f"  ❌ Falha ao consultar DataJud ({tribunal}): {e}")
            return []

    def search_all_tribunals(self, query: str) -> dict[str, list[dict]]:
        """
        Busca processos em TODOS os tribunais disponíveis.
        Útil para uma verificação completa de antecedentes.
        """
        results = {}
        for tribunal_key in DATAJUD_TRIBUNAIS:
            processes = self.search_processes(tribunal_key, query, size=5)
            if processes:
                results[tribunal_key] = processes
        
        total = sum(len(v) for v in results.values())
        logger.info(f"  📋 Total: {total} processos em {len(results)} tribunais")
        return results

    def check_improbidade(self, query: str) -> list[dict]:
        """
        Busca especificamente por processos de improbidade administrativa.
        Retorna apenas processos com assuntos relevantes.
        """
        all_matches = []
        
        for tribunal_key in DATAJUD_TRIBUNAIS:
            processes = self.search_processes(tribunal_key, query, size=20)
            for proc in processes:
                # Filter for corruption-related subjects
                assuntos = proc.get("assunto", [])
                if isinstance(assuntos, list):
                    assunto_names = [a.get("nome", "") for a in assuntos if isinstance(a, dict)]
                else:
                    assunto_names = []
                
                classes = proc.get("classe", {})
                classe_name = classes.get("nome", "") if isinstance(classes, dict) else ""
                
                is_relevant = (
                    any(a in ASSUNTOS_CORRUPTION for a in assunto_names) or
                    any(c in classe_name for c in CLASSES_IMPROBIDADE)
                )
                
                if is_relevant:
                    all_matches.append({
                        "numero_processo": proc.get("numeroProcesso", ""),
                        "tribunal": tribunal_key.upper(),
                        "classe": classe_name,
                        "assuntos": assunto_names,
                        "data_ajuizamento": proc.get("dataAjuizamento", ""),
                        "grau": proc.get("grau", "")
                    })
        
        if all_matches:
            logger.warning(f"  🚨 {len(all_matches)} processos de improbidade/corrupção encontrados!")
        else:
            logger.info(f"  ✅ Nenhum processo de improbidade encontrado para '{query}'")
        
        return all_matches

    def build_judicial_risk_score(self, name: str, cpf_cnpj: Optional[str] = None) -> dict:
        """
        Calcula um score de risco judicial baseado nos processos encontrados.
        
        Returns:
            {
                "name": "...",
                "risk_score": 0-100,
                "total_processes": N,
                "improbidade_count": N,
                "details": [...]
            }
        """
        # Search by name
        improbidade = self.check_improbidade(name)
        
        # Also search by CPF/CNPJ if provided
        if cpf_cnpj:
            improbidade_cpf = self.check_improbidade(cpf_cnpj)
            # Deduplicate by processo number
            seen = {p["numero_processo"] for p in improbidade}
            for p in improbidade_cpf:
                if p["numero_processo"] not in seen:
                    improbidade.append(p)
                    seen.add(p["numero_processo"])
        
        # Calculate risk score
        risk_score = 0
        if len(improbidade) >= 3:
            risk_score = 90
        elif len(improbidade) == 2:
            risk_score = 70
        elif len(improbidade) == 1:
            risk_score = 40
        else:
            risk_score = 0
        
        return {
            "name": name,
            "cpf_cnpj": cpf_cnpj,
            "risk_score": risk_score,
            "total_improbidade": len(improbidade),
            "processes": improbidade[:10],  # Top 10
            "source": "DataJud - Conselho Nacional de Justiça (CNJ)"
        }


if __name__ == "__main__":
    import sys
    loader = DataJudLoader()
    logger.info("=== DataJud - CNJ Loader ===")
    
    target = "Aécio Neves"
    if len(sys.argv) > 1:
        target = " ".join(sys.argv[1:])
        
    result = loader.build_judicial_risk_score(target)
    logger.info(f"  Target: {target}")
    logger.info(f"  Risk Score: {result['risk_score']}/100")
    logger.info(f"  Total Improbidade: {result['total_improbidade']}")
    if result['processes']:
        logger.info(f"  Sample Case: {result['processes'][0].get('numeroProcesso')}")
