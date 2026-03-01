import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import logging
import time
import requests
from typing import List, Dict, Any
from src.core.api_client import BackendClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def evaluate_coherence_nlp(promise_text: str, vote_summary: str, vote_choice: str) -> Dict[str, Any]:
    """
    Heuristic-based NLP Engine. 
    Analyzes intent and keywords to detect contradictions or alignments.
    """
    promise_text = promise_text.lower()
    vote_summary = vote_summary.lower()
    vote_choice = vote_choice.lower()
    
    # Intent Dictionaries
    REDUCTION = {"reduzir", "diminuir", "corte", "abaixar", "menos"}
    INCREASE = {"aumentar", "elevar", "mais", "expansão", "criação"}
    NEG_CHOICE = {"não", "contra", "rejeitar"}
    POS_CHOICE = {"sim", "favor", "aprovar"}
    
    # 1. Contradiction: Promise to reduce, but voted to increase (or vice versa)
    promise_to_reduce = any(w in promise_text for w in REDUCTION)
    vote_is_increase = any(w in vote_summary for w in INCREASE)
    
    if promise_to_reduce and vote_is_increase and vote_choice in POS_CHOICE:
        return {
            "score": -0.85, 
            "explanation": "Contradição detectada: Promessa de redução/corte confrontada com voto favorável a aumento/expansão."
        }
    
    # 2. Alignment: Promise to increase, and voted to increase
    promise_to_increase = any(w in promise_text for w in INCREASE)
    if promise_to_increase and vote_is_increase and vote_choice in POS_CHOICE:
        return {
            "score": 0.9,
            "explanation": "Alinhamento detectado: Promessa de expansão/aumento corroborada por voto favorável."
        }
        
    # 3. Topic Matching (Basic)
    TOPICS = {
        "saúde": ["saúde", "hospital", "sus", "médico"],
        "educação": ["educação", "escola", "professor", "ensino"],
        "segurança": ["segurança", "polícia", "crime", "violência"],
        "economia": ["economia", "imposto", "tributo", "fiscal"]
    }
    
    for topic, keywords in TOPICS.items():
        if any(k in promise_text for k in keywords) and any(k in vote_summary for k in keywords):
            if vote_choice in POS_CHOICE:
                return {"score": 0.5, "explanation": f"Alinhamento temático na área de {topic}."}
            else:
                return {"score": -0.3, "explanation": f"Divergência temática na área de {topic}."}

    return {"score": 0.0, "explanation": "Não foi possível determinar correlação direta entre o texto da promessa e o resumo da votação."}

class CoherenceWorker:
    def __init__(self):
        self.backend = BackendClient()
        self.public_api_url = "http://localhost:8080/api/v1"

    def fetch_all_politicians(self) -> List[Dict[str, Any]]:
        url = f"{self.public_api_url}/politicians/search?name="
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch politicians: {e}")
            return []

    def fetch_politician_details(self, pid: int) -> Dict[str, Any]:
        url = f"{self.public_api_url}/politicians/{pid}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch details for {pid}: {e}")
            return {}

    def run(self):
        logger.info("Starting Coherence Analysis...")
        politicians = self.fetch_all_politicians()
        logger.info(f"Found {len(politicians)} politicians to process.")

        for p_slim in politicians:
            p = self.fetch_politician_details(p_slim["id"])
            if not p:
                continue

            promises = p.get("promises", [])
            votes = p.get("votes", [])
            external_id = p.get("externalId")

            if not promises or not votes:
                logger.info(f"Skipping {p.get('name')} (Missing promises or votes).")
                continue

            logger.info(f"Analyzing {p.get('name')} ({len(promises)} promises, {len(votes)} votes)")

            for vote in votes:
                # If already scored, we can skip to save LLM tokens
                if vote.get("coherenceScore") is not None:
                    continue

                best_score = 0.0
                best_explanation = "Sem correlação com qualquer promessa."
                
                # Check against all promises (in reality, use embeddings search first)
                for promise in promises:
                    eval_result = evaluate_coherence_nlp(promise.get("text", ""), vote.get("propositionSummary", ""), vote.get("voteChoice", ""))
                    if abs(eval_result["score"]) > abs(best_score):
                        best_score = eval_result["score"]
                        best_explanation = f"Baseado na promessa '{promise.get('text')[:30]}...': {eval_result['explanation']}"
                
                # Update the backend with the NLP result
                vote_payload = {
                    "propositionExternalId": vote.get("propositionExternalId"),
                    "voteChoice": vote.get("voteChoice"),
                    "propositionSummary": vote.get("propositionSummary"),
                    "coherenceScore": best_score,
                    "coherenceExplanation": best_explanation
                }
                logger.info(f" -> Saving Coherence for vote '{vote.get('propositionExternalId')}': Score {best_score}")
                self.backend.ingest_vote(external_id, vote_payload)
                time.sleep(0.5)

if __name__ == "__main__":
    worker = CoherenceWorker()
    worker.run()
