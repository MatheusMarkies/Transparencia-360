import asyncio
import logging
import json
import os
from pathlib import Path
from src.core.api_client import GovAPIClient, BackendClient
from src.extractors.camara_extractor import CamaraExtractor
from src.extractors.querido_diario_extractor import QueridoDiarioExtractor
from src.nlp.spacy_ner import SpacyEngine
from src.analyzers.cross_matcher import CrossMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentaryEvidenceWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.camara_ext = CamaraExtractor()
        self.gazette_ext = QueridoDiarioExtractor()
        self.nlp_engine = SpacyEngine()
        self.matcher = CrossMatcher()

    async def _process_politician(self, deputy_id: int, name: str):
        logger.info(f"  Processing documentary evidence for {name} ({deputy_id})...")
        
        # 1. Extraction (Camara)
        extraction_results = await self.camara_ext.process_deputy(deputy_id)
        if not extraction_results:
            logger.info(f"    No documents found for {name}.")
            return []

        # 2. NLP Analysis
        nlp_results = []
        for ext in extraction_results:
            local_file = ext['prova_documental']['arquivo_local']
            analysis = self.nlp_engine.analyze_document(local_file)
            if analysis:
                analysis['file'] = local_file
                nlp_results.append(analysis)
        
        # 3. Cross-Match & JSON Report
        report_path = self.matcher.generate_proof_json(name, extraction_results, nlp_results)
        logger.info(f"    ✅ Audit report generated: {os.path.basename(report_path)}")
        
        # 4. Integrate alerts into Backend (Staff Anomaly Details)
        # We append these findings to the existing staffAnomalyDetails or create a new exhibit field
        anomaly_count = len(extraction_results)
        exhibits = []
        for res in extraction_results:
            exhibits.append({
                "type": "DESPESA_FISCAL",
                "severity": "MEDIUM",
                "detail": f"Documento extraído: {res['metadados']['fornecedor']}",
                "totalValue": res['metadados']['valor'],
                "doc_path": res['prova_documental']['arquivo_local'],
                "evidence_url": res['prova_documental']['onde_esta_essa_info_url']
            })

        # Push to backend
        self.backend.ingest_politician({
            "externalId": f"camara_{deputy_id}",
            "name": name,
            "staffAnomalyCount": anomaly_count, # Simplified: reusing anomaly count for now
            "staffAnomalyDetails": json.dumps(exhibits, ensure_ascii=False)
        })
        
        return exhibits

    def run(self, limit: int = 50):
        """Sequential processing due to I/O and PDF reading overhead."""
        logger.info("=== Documentary Evidence Worker - Deterministic NLP & Audit Trail ===")
        
        # Fetch deputies list from Camara API (Standard Pattern) — Simplified for now
        # Ideally would use cached list from step 1
        camara_api = GovAPIClient("https://dadosabertos.camara.leg.br/api/v2")
        resp = camara_api.get("deputados", params={"ordem": "ASC", "ordenarPor": "nome"})
        deputies = resp.get("dados", [])[:limit]
        
        for dep in deputies:
            asyncio.run(self._process_politician(dep['id'], dep['nome']))
            
        logger.info("=== Documentary Evidence Worker Complete ===")

if __name__ == "__main__":
    worker = DocumentaryEvidenceWorker()
    worker.run(limit=5)
