"""
Super Report Worker - O Cérebro da Operação (Gerador de Dossiês)

Estratégia:
Lê os relatórios isolados de cada módulo (Rosie, Absences, etc.) no Data Lake
e compila um dossiê pronto para a IA analisar.
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
                    return json.load(f)
            except Exception as e:
                logger.error(f"  ❌ Erro ao ler faltas para {name}: {e}")
        return {}

    def generate_detective_prompt(self, base_data: dict, rosie_data: dict, absences_data: dict) -> str:
        """
        Gera o Prompt de Mestre para a LLM investigar os dados estruturados.
        """
        nome = base_data.get("name", "Desconhecido")
        
        # Montar secção da Rosie (Gastos)
        rosie_text = "Sem dados anómalos detetados na cota parlamentar."
        if rosie_data and rosie_data.get("total_anomalias", 0) > 0:
            score = rosie_data.get("risco_score", 0)
            rosie_text = f"ALERTA DE RISCO CEAP: Nível {score}/100. Foram detetadas {rosie_data['total_anomalias']} anomalias pelo motor de IA.\n\nPrincipais suspeitas levantadas:\n"
            
            for anomalia in rosie_data.get("principais_anomalias", [])[:5]:
                clf = anomalia.get('classifier', 'Desconhecido')
                motivo = anomalia.get('reason', 'Sem justificação')
                rosie_text += f"- [{clf}]: {motivo}\n"

        # Montar secção de Faltas
        faltas_text = "Sem dados de assiduidade."
        if absences_data:
            anos = sorted([k for k in absences_data.keys() if k.isdigit()], reverse=True)
            if anos:
                ano_recente = anos[0]
                dados_ano = absences_data[ano_recente]
                presencas = dados_ano.get('presencas_totais', 0)
                faltas = dados_ano.get('faltas_estimadas', 0)
                sessoes = dados_ano.get('sessoes_legislativas_totais', 0)
                faltas_text = f"Ano {ano_recente}: Esteve presente em {presencas} sessões de um total de {sessoes} (Faltas estimadas: {faltas})."

        prompt = f"""Você é um Investigador Sênior da Polícia Federal do Brasil e Auditor Especialista em Dados do TCU. O seu foco é investigar crimes financeiros, peculato (rachadinha), lavagem de dinheiro e o uso indevido de verbas públicas.

Analise o dossiê de dados do parlamentar abaixo. NÃO INVENTE DADOS. Baseie-se ESTRITAMENTE nas evidências apresentadas.

--- ALVO DA INVESTIGAÇÃO ---
Nome: {nome}
ID Câmara: {base_data.get('id', 'N/A')}

--- RELATÓRIO DO MOTOR DE IA DE NOTAS FISCAIS (ROSIE) ---
{rosie_text}

--- ASSIDUIDADE EM PLENÁRIO ---
{faltas_text}

--- TAREFA ---
1. Faça uma avaliação de risco de corrupção ou uso indevido de dinheiro público (Baixo, Médio, Alto, Crítico).
2. Destaque os pontos mais alarmantes (se houver) com base nos relatórios de IA e nas faltas.
3. Sugira 2 a 3 linhas de investigação que um auditor humano deveria seguir para confirmar estas suspeitas.

Gere a resposta num tom estritamente profissional, técnico e imparcial.
"""
        return prompt

    def run(self, limit: int = 15):
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║  📑 SUPER REPORT WORKER — Integração Total de Dossiês  ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")

        try:
            # Em vez de ir ao Backend, descobre quem processar lendo os ficheiros da Rosie!
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

                # 2. Carregar as faltas do Data Lake local
                absences_data = self._load_absences_dossier(name, dep_id)

                # 3. Gerar Dossiê de Dados Consolidados
                dossier = {
                    "metadata": {
                        "gerado_em": datetime.now().isoformat(),
                        "deputado_id": dep_id,
                        "nome": name
                    },
                    "evidencias_rosie": rosie_data,
                    "evidencias_assiduidade": absences_data
                }

                # 4. Gerar o Prompt da LLM
                prompt_para_llm = self.generate_detective_prompt(base_data, rosie_data, absences_data)
                dossier["00_llm_detective_prompt"] = prompt_para_llm

                # 5. Gravar no Disco
                safe_name = self._get_safe_name(name)
                filename = f"super_report_{safe_name}_{dep_id}.json"
                filepath = REPORTS_DIR / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(dossier, f, indent=4, ensure_ascii=False)

                risco_rosie = rosie_data.get("risco_score", 0)
                logger.info(f"  ✅ Dossiê compilado: {name} (Risco Rosie: {risco_rosie:.1f}/100) -> Salvo em {filename}")

        except Exception as e:
            logger.error(f"❌ Falha crítica no SuperReportWorker: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera o Super Dossiê Integrando todos os Workers")
    parser.add_argument("--limit", type=int, default=15, help="Número de políticos a analisar")
    args = parser.parse_args()

    worker = SuperReportWorker()
    worker.run(limit=args.limit)