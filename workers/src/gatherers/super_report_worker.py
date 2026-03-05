"""
Super Report Worker - O Cérebro da Operação (Gerador de Dossiês)

Estratégia:
Lê os relatórios isolados de cada módulo (Rosie, Absences, etc.) no Data Lake,
filtra detalhes pesados desnecessários (como listas de sessões diárias ou spam de Benford) e 
compila um dossiê super concentrado e pronto para a IA analisar.
"""

import logging
import json
import argparse
import glob
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("super_report_worker")

# =============================================================================
# CONFIGURAÇÃO DE DATA LAKES (CAMINHOS ABSOLUTOS REAIS)
# =============================================================================
WORKER_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REPORTS_DIR = WORKER_ROOT / "data" / "processed" / "super_reports"
ROSIE_REPORTS_DIR = WORKER_ROOT / "data" / "processed" / "rosie_reports"
ABSENCES_DIR = WORKER_ROOT / "data" / "absences"

class SuperReportWorker:
    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_safe_name(self, name: str) -> str:
        """Formata o nome para bater certinho com o formato dos ficheiros guardados."""
        return name.replace(" ", "_").replace("/", "_").lower()

    def _load_rosie_dossier(self, name: str, dep_id: str) -> dict:
        safe_name = self._get_safe_name(name)
        filepath = ROSIE_REPORTS_DIR / f"rosie_report_{safe_name}_{dep_id}.json"
        
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"  ❌ Erro ao ler laudo da Rosie para {name}: {e}")
        return {}

    def _load_absences_dossier(self, name: str, dep_id: str) -> dict:
        safe_name = self._get_safe_name(name)
        filepath = ABSENCES_DIR / f"absences_{safe_name}_{dep_id}.json"
        
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    dados_completos = json.load(f)
                    # Retorna apenas o resumo!
                    return dados_completos.get("resumo", {})
            except Exception as e:
                logger.error(f"  ❌ Erro ao ler faltas para {name}: {e}")
        return {}

    def generate_detective_prompt(self, base_data: dict, rosie_data: dict, absences_data: dict) -> str:
        """
        Gera o Prompt passando os dados em JSON puro para a LLM interpretar.
        """
        import json
        
        # Converte os dicionários Python para strings JSON formatadas
        json_base = json.dumps(base_data, indent=2, ensure_ascii=False)
        
        if not rosie_data:
            json_rosie = '{"status": "Sem anomalias detetadas"}'
        else:
            json_rosie = json.dumps(rosie_data, indent=2, ensure_ascii=False)

        if not absences_data:
            json_faltas = '{"status": "Sem dados de assiduidade"}'
        else:
            json_faltas = json.dumps(absences_data, indent=2, ensure_ascii=False)

        prompt = f"""Você é um Investigador Sênior da Polícia Federal do Brasil e Auditor Especialista em Dados do TCU. 
O seu foco é investigar crimes financeiros, peculato (rachadinha), lavagem de dinheiro e o uso indevido de verbas públicas.

Abaixo estão três blocos de dados estruturados em formato JSON referentes a um parlamentar.
NÃO INVENTE DADOS. Baseie-se ESTRITAMENTE nos valores contidos nestes JSONs.

=== BLOCO 1: DADOS CADASTRAIS ===
{json_base}

=== BLOCO 2: LAUDO DE ANOMALIAS (MOTOR IA ROSIE) ===
{json_rosie}

=== BLOCO 3: HISTÓRICO DE ASSIDUIDADE (RESUMO ANUAL) ===
{json_faltas}

--- TAREFA ---
Leia os JSONs acima e gere um laudo investigativo contendo:
1. Nível de Risco Geral (Baixo, Médio, Alto, Crítico) justificado pelos dados.
2. Descrição das principais anomalias financeiras (se o total_anomalias for > 0 no Bloco 2).
3. Avaliação do custo-benefício do parlamentar (cruzando os gastos com a assiduidade no Bloco 3).
4. Sugestão de 2 a 3 linhas de investigação formais baseadas nos fornecedores ou padrões suspeitos encontrados no JSON.

Gere a resposta num tom estritamente profissional, técnico e forense.
"""
        return prompt

    def run(self, limit: int = 15):
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║  📑 SUPER REPORT WORKER — Integração Total de Dossiês  ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")

        try:
            # Descobre quem processar lendo os ficheiros da Rosie!
            rosie_files = glob.glob(str(ROSIE_REPORTS_DIR / "rosie_report_*.json"))
            
            if not rosie_files:
                logger.warning("Nenhum relatório da Rosie encontrado. Rode a IA primeiro.")
                return

            # Limita a execução
            rosie_files = rosie_files[:limit]
            logger.info(f"  🔍 A compilar dossiês com base em {len(rosie_files)} relatórios encontrados...")

            for file_path in rosie_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    rosie_data = json.load(f)
                
                name = rosie_data.get("deputado_nome", "Desconhecido")
                dep_id = str(rosie_data.get("deputado_id", "0"))
                
                # 1. Carregar os dados base 
                base_data = {"name": name, "id": dep_id}

                # 2. Carregar as faltas do Data Lake local bruto
                absences_data_raw = self._load_absences_dossier(name, dep_id)

                # =========================================================
                # MÁGICA DE OTIMIZAÇÃO: Filtrar detalhes e gerar um resumo
                # =========================================================
                absences_summary = {}
                if absences_data_raw:
                    for year, data in absences_data_raw.items():
                        if isinstance(data, dict):
                            absences_summary[year] = {
                                "ano": data.get("ano", year),
                                "sessoes_legislativas_totais": data.get("sessoes_legislativas_totais", 0),
                                "presencas_totais": data.get("presencas_totais", 0),
                                "faltas_estimadas": data.get("faltas_estimadas", 0)
                            }
                
                # =========================================================
                # COMPRESSÃO ROSIE: Resumir spam da Lei de Benford
                # =========================================================
                if rosie_data and "todas_anomalias_detalhadas" in rosie_data:
                    anomalias = rosie_data["todas_anomalias_detalhadas"]
                    
                    # Separa as anomalias da Lei de Benford das restantes
                    benford_items = [a for a in anomalias if a.get("classifier") == "BenfordLawClassifier"]
                    outras_anomalias = [a for a in anomalias if a.get("classifier") != "BenfordLawClassifier"]
                    
                    # Se existirem alertas de Benford, cria apenas 1 item consolidado
                    if benford_items:
                        ref = benford_items[0]
                        resumo_benford = {
                            "is_suspicious": True,
                            "classifier": "BenfordLawClassifier",
                            "confidence": ref.get("confidence"),
                            "reason": f"RESUMO COMPACTO: O modelo matemático sinalizou em bloco {len(benford_items)} notas fiscais. {ref.get('reason')}",
                            "details": ref.get("details"),
                            "deputy_id": dep_id
                        }
                        outras_anomalias.append(resumo_benford)
                        
                    # Sobrescreve a lista longa com a lista limpa e comprimida
                    rosie_data["todas_anomalias_detalhadas"] = outras_anomalias

                # 3. Gerar Dossiê de Dados Consolidados Limpos
                dossier = {
                    "metadata": {
                        "gerado_em": datetime.now().isoformat(),
                        "deputado_id": dep_id,
                        "nome": name
                    },
                    "evidencias_rosie": rosie_data,
                    "evidencias_assiduidade": absences_summary
                }

                # 4. Gerar o Prompt da LLM
                prompt_para_llm = self.generate_detective_prompt(base_data, rosie_data, absences_summary)
                dossier["00_llm_detective_prompt"] = prompt_para_llm

                # 5. Gravar no Disco
                safe_name = self._get_safe_name(name)
                filename = f"super_report_{safe_name}_{dep_id}.json"
                filepath = REPORTS_DIR / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(dossier, f, indent=4, ensure_ascii=False)

                risco_rosie = rosie_data.get("risco_score", 0)
                logger.info(f"  ✅ Dossiê compilado e compactado: {name} (Risco Rosie: {risco_rosie:.1f}/100) -> Salvo em {filename}")

        except Exception as e:
            logger.error(f"❌ Falha crítica no SuperReportWorker: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera o Super Dossiê Integrando todos os Workers")
    parser.add_argument("--limit", type=int, default=15, help="Número de políticos a analisar")
    args = parser.parse_args()

    worker = SuperReportWorker()
    worker.run(limit=args.limit)