import logging
import json
import requests
import argparse
import csv
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração de caminhos absolutos
CURRENT_DIR = Path(__file__).resolve().parent
WORKER_ROOT = CURRENT_DIR.parent.parent
REPORTS_DIR = WORKER_ROOT / "data" / "processed" / "super_reports"
ROSIE_CSV_PATH = WORKER_ROOT / "data" / "processed" / "rosie_anomalies.csv"

class SuperReportWorker:
    def __init__(self):
        self.base_url = "http://localhost:8080/api/v1/politicians"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def generate_detective_prompt(self, dossier_data):
        """
        Gera a string exata (o Prompt) que será enviada para a API da LLM no futuro.
        Nesta fase, apenas construímos o texto para validação humana.
        """
        prompt = f"""Você é um Investigador Sênior da Polícia Federal do Brasil e Auditor Especialista em Dados do TCU. O seu foco é investigar crimes financeiros, peculato (rachadinha), lavagem de dinheiro e o uso de notas frias na Cota Parlamentar (CEAP).

Analise o dossiê de dados do parlamentar abaixo. NÃO INVENTE DADOS. Baseie-se EXCLUSIVAMENTE nos números e anomalias fornecidos no JSON.

Preste atenção máxima à secção '05_auditoria_matematica_rosie'. A quebra da Lei de Benford indica fortemente a fabricação manual de notas fiscais (notas frias). Gastos repetidos idênticos (duplicatas) ou gastos em hotéis aos fins de semana apontam para desvio de finalidade.

Elabore um Relatório de Inteligência Policial rigoroso e direto contendo:
1. **Hipótese Investigativa:** Baseado na auditoria matemática e nas anomalias contratuais, qual é o provável modus operandi do esquema em andamento? (Ex: Fabricação de notas frias para saque em espécie, financiamento de campanhas ocultas, turismo com dinheiro público).
2. **Materialidade (Red Flags):** Liste em bullet points as 3 a 5 maiores provas matemáticas ou flagrantes encontrados nos dados (cite a quebra de Benford, valores duplicados exatos, datas anômalas, etc).
3. **Recomendação de Quebra de Sigilo:** Onde um delegado da PF deve focar a próxima fase da investigação física para materializar o crime? (ex: quebrar sigilo bancário de quem? buscar notas originais de qual fornecedor?).

DADOS DO PARLAMENTAR (JSON):
{json.dumps(dossier_data, indent=2, ensure_ascii=False)}

Responda obrigatoriamente em formato Markdown profissional e policial.
"""
        return prompt

    def run(self, limit=50):
        logger.info("=== Gerando Dossiês para IA (Integrando Motor Rosie e Provas) ===")
        try:
            # 1. Pega os deputados do Backend
            resp = requests.get(f"{self.base_url}/search?name=")
            if resp.status_code != 200:
                logger.error(f"Erro ao buscar políticos da API: HTTP {resp.status_code}")
                return
            
            politicians = resp.json()
            
            # Ordena pelos mais suspeitos primeiro!
            politicians = sorted(politicians, key=lambda x: float(x.get('overallRiskScore') or 0), reverse=True)[:limit]
            
            # 2. PRÉ-CARREGA AS PROVAS TEXTUAIS DA ROSIE PARA MEMÓRIA
            rosie_data = {}
            if ROSIE_CSV_PATH.exists():
                with open(ROSIE_CSV_PATH, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        dep_id = row.get('deputy_id', '')
                        if dep_id not in rosie_data:
                            rosie_data[dep_id] = []
                        # Guarda apenas as 15 primeiras fraudes de cada um para não estourar a memória (tokens) da IA
                        if len(rosie_data[dep_id]) < 15:
                            rosie_data[dep_id].append({
                                "classificador_tecnico": row.get('classifier', ''),
                                "prova_textual": row.get('reason', '')
                            })
            else:
                logger.warning(f"Ficheiro de anomalias {ROSIE_CSV_PATH} não encontrado. Execute o rosie_worker.py primeiro!")

            for p in politicians:
                pol_id = p.get('id')
                name = p.get('name')
                risk_score = p.get('overallRiskScore', 0)
                
                logger.info(f"\n🔍 Compilando dossiê de {name} (Risco Global: {risk_score})")
                
                # 3. Busca Detalhes Consolidados e Grafo
                details_resp = requests.get(f"{self.base_url}/{pol_id}")
                graph_resp = requests.get(f"{self.base_url}/{pol_id}/graph")
                
                details = details_resp.json() if details_resp.status_code == 200 else p
                graph_data = graph_resp.json() if graph_resp.status_code == 200 else {"nodes": [], "links": []}
                
                # 4. Contagem Inteligente de Documentos no Grafo
                nodes = graph_data.get('nodes', [])
                despesas_count = sum(1 for n in nodes if 'Despesa' in str(n.get('group', '')) or 'R$' in str(n.get('name', '')))
                empresas_count = sum(1 for n in nodes if 'Empresa' in str(n.get('group', '')) or 'Fornecedor' in str(n.get('name', '')))
                municipios_count = sum(1 for n in nodes if 'Municipio' in str(n.get('group', '')) or 'Município' in str(n.get('name', '')))
                promessas_count = sum(1 for n in nodes if 'Promessa' in str(n.get('group', '')) or 'Promessa:' in str(n.get('name', '')))
                votos_count = sum(1 for n in nodes if 'Votou' in str(n.get('name', '')))

                def safe_json_load(data_string):
                    if not data_string: return []
                    try: return json.loads(data_string)
                    except: return str(data_string)

                # Busca as provas exatas no CSV que carregámos
                ext_id_clean = details.get("externalId", "").replace("camara_", "")
                evidencias_rosie_textuais = rosie_data.get(ext_id_clean, [])

                # 5. Monta a Estrutura do Dossiê Gigante
                dossier = {
                    "01_metadados": {
                        "camara_id": details.get("externalId"),
                        "nome": name,
                        "partido_estado": f"{details.get('party')} - {details.get('state')}",
                        "risco_global": risk_score,
                        "data_extracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "02_documentos_lidos_e_grafos": {
                        "notas_fiscais_agrupadas": despesas_count,
                        "empresas_qsa_e_contratos_mapeados": empresas_count,
                        "municipios_recebedores_de_emendas": municipios_count,
                        "promessas_campanha_identificadas": promessas_count,
                        "votacoes_analisadas_nlp": votos_count
                    },
                    "03_estatisticas_patrimoniais_e_uso_maquina": {
                        "total_gasto_cota_parlamentar": details.get("expenses"),
                        "taxa_ausencia_plenario": details.get("absences"),
                        "presencas_plenario": details.get("presences"),
                        "patrimonio_declarado_2022": details.get("declaredAssets"),
                        "fator_anomalia_patrimonial": details.get("wealthAnomaly")
                    },
                    "04_alertas_de_inteligencia": {
                        "motor_rachadinha_score": details.get("cabinetRiskScore"),
                        "motor_rachadinha_evidencias": safe_json_load(details.get("cabinetRiskDetails")),
                        "anomalias_contratacao_gabinete_qtd": details.get("staffAnomalyCount"),
                        "anomalias_contratacao_gabinete_evidencias": safe_json_load(details.get("staffAnomalyDetails")),
                        "mencoes_suspeitas_diarios_oficiais": details.get("nlpGazetteCount"),
                        "processos_judiciais_improbidade": details.get("judicialRiskScore")
                    },
                    "05_auditoria_matematica_rosie": {
                        "quebra_lei_de_benford_qtd": details.get("rosieBenfordCount") or 0,
                        "reembolsos_duplicados_qtd": details.get("rosieDuplicateCount") or 0,
                        "gastos_turismo_fim_de_semana_qtd": details.get("rosieWeekendCount") or 0,
                        "evidencias_textuais_extraidas_das_notas": evidencias_rosie_textuais
                    }
                }
                
                # 6. Geração do Prompt final
                prompt_para_llm = self.generate_detective_prompt(dossier)
                
                final_report = dossier.copy()
                final_report["06_llm_detective_prompt"] = prompt_para_llm
                
                # 7. Salva no Disco
                filename = f"super_report_{name.replace(' ', '_').lower()}_{details.get('externalId')}.json"
                filepath = REPORTS_DIR / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(final_report, f, indent=4, ensure_ascii=False)
                    
                logger.info(f"  ✅ Dossiê e Prompt salvos em: {filename}")
                
        except Exception as e:
            logger.error(f"Erro ao gerar super relatórios: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera o Dossiê e prepara o Prompt para LLM")
    parser.add_argument("--limit", type=int, default=15, help="Número de parlamentares para gerar relatório")
    args = parser.parse_args()
    
    worker = SuperReportWorker()
    worker.run(limit=args.limit)