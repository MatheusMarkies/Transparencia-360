import asyncio
import os
from src.extractors.camara_extractor import CamaraExtractor
from src.nlp.spacy_ner import SpacyEngine
from src.analyzers.cross_matcher import CrossMatcher

async def main():
    print("🚀 Starting Phase 1 Integration Test...")
    
    # 1. Extraction (Camara)
    print("Step 1: Extracting parliamentary expenses for ID 160569 (Arthur Lira)...")
    extractor = CamaraExtractor()
    extraction_results = await extractor.process_deputy(160569)
    print(f"✅ Found {len(extraction_results)} expenses with documents.")
    
    if not extraction_results:
        print("❌ No documents found to analyze. Aborting.")
        return

    # 2. NLP Analysis
    print("Step 2: Running Offline NLP (spaCy + Regex) on downloaded PDFs...")
    engine = SpacyEngine()
    nlp_results = []
    
    for ext in extraction_results:
        local_file = ext['prova_documental']['arquivo_local']
        print(f"  Analyzing {os.path.basename(local_file)}...")
        analysis = engine.analyze_document(local_file)
        if analysis:
            analysis['file'] = local_file
            nlp_results.append(analysis)
            print(f"    - Keywords found: {analysis['keywords_found']}")
            print(f"    - Entities extracted: {len(analysis['entities'])}")
    
    # 3. Cross-Match & JSON Report
    print("Step 3: Generating Final Audit JSON...")
    matcher = CrossMatcher()
    report_path = matcher.generate_proof_json("Arthur Lira", extraction_results, nlp_results)
    
    print(f"✨ SUCCESS! Final report generated at: {report_path}")
    print("\n--- JSON Snippet ---")
    with open(report_path, "r", encoding="utf-8") as f:
        print(f.read()[:500] + "...")

if __name__ == "__main__":
    # Ensure working directory is workers
    asyncio.run(main())
