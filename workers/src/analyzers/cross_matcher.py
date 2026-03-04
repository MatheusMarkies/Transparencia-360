import json
from pathlib import Path
from datetime import datetime

class CrossMatcher:
    def __init__(self):
        self.output_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_proof_json(self, politician_name: str, extraction_results: list, nlp_results: list):
        """
        Gera o JSON final seguindo o formato rigoroso de auditoria.
        """
        final_reports = []
        
        for ext in extraction_results:
            # Match NLP results for this specific local file if available
            local_nlp = next((n for n in nlp_results if n['file'] == ext['prova_documental']['arquivo_local']), None)
            
            report = {
                "alerta": ext.get("alerta", "SUSPEITA_GERAL"),
                "prova_documental": ext["prova_documental"],
                "prova_societaria": {
                    "empresa": ext["metadados"].get("fornecedor", "DESCONHECIDO"),
                    "cnpjs": [ext["metadados"].get("cnpj")],
                    "onde_esta_essa_info_url": f"https://brasilapi.com.br/api/cnpj/v1/{ext['metadados'].get('cnpj')}"
                }
            }
            
            if local_nlp:
                report["detalhes_ner"] = local_nlp["entities"]
                report["regex_extraidos"] = local_nlp["regex_hits"]

            final_reports.append(report)

        # Save to disk
        filename = f"report_{politician_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        target_path = self.output_dir / filename
        
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(final_reports, f, indent=2, ensure_ascii=False)
            
        return str(target_path)

if __name__ == "__main__":
    matcher = CrossMatcher()
    print("CrossMatcher ready.")
