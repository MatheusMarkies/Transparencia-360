import spacy
import fitz # PyMuPDF
import os
from pathlib import Path
from src.nlp.regex_patterns import KEYWORDS_SUSPICIOUS, find_patterns, get_context_window

class SpacyEngine:
    def __init__(self):
        # Load the Portuguese model
        try:
            self.nlp = spacy.load("pt_core_news_lg")
        except Exception as e:
            print(f"Model not found. Run 'python -m spacy download pt_core_news_lg' first. Error: {e}")
            self.nlp = None

    def extract_text_from_pdf(self, pdf_path: str):
        text = ""
        try:
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
        return text

    def analyze_document(self, pdf_path: str):
        if not self.nlp:
            return None
            
        full_text = self.extract_text_from_pdf(pdf_path)
        if not full_text:
            return None

        analysis = {
            "keywords_found": [],
            "entities": [],
            "regex_hits": find_patterns(full_text)
        }

        for kw in KEYWORDS_SUSPICIOUS:
            window = get_context_window(full_text, kw)
            if window:
                analysis["keywords_found"].append(kw)
                # Use spaCy for NER in this window
                doc = self.nlp(window)
                for ent in doc.ents:
                    if ent.label_ in ["PER", "ORG"]:
                        analysis["entities"].append({
                            "text": ent.text,
                            "type": ent.label_,
                            "context": kw
                        })
        
        # Deduplicate entities
        analysis["entities"] = [dict(t) for t in {tuple(d.items()) for d in analysis["entities"]}]
        return analysis

if __name__ == "__main__":
    engine = SpacyEngine()
    # Test with a dummy path if exists
    test_pdf = "data/downloads/notas_fiscais/test.pdf"
    if os.path.exists(test_pdf):
        print(engine.analyze_document(test_pdf))
