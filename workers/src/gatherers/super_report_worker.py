import logging
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).resolve().parent
WORKER_ROOT = CURRENT_DIR.parent.parent
REPORTS_DIR = WORKER_ROOT / "data" / "processed" / "super_reports"

class SuperReportWorker:
    def __init__(self):
        self.base_url = "http://localhost:8080/api/v1/politicians"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def generate_detective_prompt(self, dossier_data):
        """
        Gera a string exata (o Prompt) que será enviada para a API da LLM no futuro.
        Nesta fase, apenas construímos o texto para validação humana.
        """
        prompt = f"""Você é um Investigador Sênior da Polícia Federal do Brasil e Auditor do TCU, especialista em crimes financeiros, peculato (rachadinha), lavagem de dinheiro e fraude à licitação.

Analise o dossiê de dados do parlamentar abaixo. NÃO INVENTE DADOS. Baseie-se EXCLUSIVAMENTE nos números e anomalias fornecidos no JSON.

Elabore um Relatório de Inteligência Policial rigoroso e direto contendo:
1. **Hipótese Investigativa:** Baseado nas anomalias matemáticas, qual é o provável esquema em andamento? (Se os dados estiverem limpos, seja honesto e diga que não há indícios de fraude).
2. **Red Flags (Sinais de Alerta):** Liste em bullet points os 3 maiores cruzamentos suspeitos encontrados nos dados.
3. **Recomendação de Diligência:** Onde um auditor ou repórter investigativo deve procurar as próximas provas físicas (ex: quebrar sigilo de qual empresa, buscar imagens de qual rua, verificar folha de ponto de qual mês).

DADOS DO PARLAMENTAR (JSON):
{json.dumps(dossier_data, indent=2, ensure_ascii=False)}

Responda em formato Markdown bem formatado.
"""
        return prompt

    def run(self, limit=50):
        logger.info("=== Gerando Dossiês para IA (Modo Preparação de Prompt) ===")
        try:
            # 1. Pega os deputados
            resp = requests.get(f"{self.base_url}/search?name=")
            if resp.status_code != 200:
                logger.error(f"Erro ao buscar políticos da API: HTTP {resp.status_code}")
                return
            
            politicians = resp.json()
            
            # Ordena pelos mais suspeitos primeiro (maior score de risco)!
            # Usamos float() e fallback para 0 caso o valor seja None
            politicians = sorted(politicians, key=lambda x: float(x.get('overallRiskScore') or 0), reverse=True)[:limit]
            
            for p in politicians:
                pol_id = p.get('id')
                name = p.get('name')
                risk_score = p.get('overallRiskScore', 0)
                
                logger.info(f"\n🔍 Compilando dossiê de {name} (Risco Global: {risk_score})")
                
                # 2. Busca Detalhes Consolidados e Grafo
                details_resp = requests.get(f"{self.base_url}/{pol_id}")
                graph_resp = requests.get(f"{self.base_url}/{pol_id}/graph")
                
                details = details_resp.json() if details_resp.status_code == 200 else p
                graph_data = graph_resp.json() if graph_resp.status_code == 200 else {"nodes": [], "links": []}
                
                # 3. Contagem Inteligente de Documentos no Grafo
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

                # 4. Monta a Estrutura do Dossiê (O que a IA vai ler)
                dossier = {
                    "01_metadados": {
                        "internal_id": pol_id,
                        "camara_id": details.get("externalId"),
                        "nome": name,
                        "partido_estado": f"{details.get('party')} - {details.get('state')}",
                        "risco_global": details.get("overallRiskScore"),
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
                    }
                }
                
                # 5. Geração do Prompt
                prompt_para_llm = self.generate_detective_prompt(dossier)
                
                # Anexa o Dossiê e o Prompt final no relatório para o Dev revisar
                final_report = dossier.copy()
                final_report["05_llm_detective_prompt"] = prompt_para_llm
                
                # 6. Salva no Disco
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