import logging
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração de caminhos absolutos
CURRENT_DIR = Path(__file__).resolve().parent
WORKER_ROOT = CURRENT_DIR.parent.parent
REPORTS_DIR = WORKER_ROOT / "data" / "processed" / "super_reports"

class SuperReportWorker:
    def __init__(self):
        self.base_url = "http://localhost:8080/api/v1/politicians"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, limit=50):
        logger.info("=== Gerando Super Relatórios Unificados (QA & Auditoria) ===")
        try:
            # 1. Pega os deputados que sobreviveram a todo o pipeline
            resp = requests.get(f"{self.base_url}/search?name=")
            if resp.status_code != 200:
                logger.error(f"Erro ao buscar políticos da API: HTTP {resp.status_code}")
                return
            
            politicians = resp.json()
            # Força ordem alfabética para bater exatamente com o Acácio Favacho da API da Câmara
            politicians = sorted(politicians, key=lambda x: str(x.get('name', '')))[:limit]
            
            for p in politicians:
                pol_id = p.get('id')
                name = p.get('name')
                
                # 2. Busca Detalhes Consolidados e Grafo
                details_resp = requests.get(f"{self.base_url}/{pol_id}")
                graph_resp = requests.get(f"{self.base_url}/{pol_id}/graph")
                
                details = details_resp.json() if details_resp.status_code == 200 else p
                graph_data = graph_resp.json() if graph_resp.status_code == 200 else {"nodes": [], "links": []}
                
                # 3. Contagem Inteligente de Documentos no Grafo
                nodes = graph_data.get('nodes', [])
                
                # Conta quantos fornecedores/notas fiscais viraram agrupamentos
                despesas_count = sum(1 for n in nodes if 'Despesa' in str(n.get('group', '')) or 'R$' in str(n.get('name', '')))
                
                # Conta empresas rastreadas (seja via QSA ou PNCP)
                empresas_count = sum(1 for n in nodes if 'Empresa' in str(n.get('group', '')) or 'Fornecedor' in str(n.get('name', '')))
                
                # Conta municípios que receberam emendas
                municipios_count = sum(1 for n in nodes if 'Municipio' in str(n.get('group', '')) or 'Município' in str(n.get('name', '')))
                
                # Conta as promessas eleitorais extraídas
                promessas_count = sum(1 for n in nodes if 'Promessa' in str(n.get('group', '')) or 'Promessa:' in str(n.get('name', '')))

                # 4. Tenta decodificar de forma segura os JSONs salvos como string no banco
                def safe_json_load(data_string):
                    if not data_string: return []
                    try: return json.loads(data_string)
                    except: return str(data_string)
                
                # Conta os votos processados com inteligência artificial
                votos_count = sum(1 for n in nodes if 'Votou' in str(n.get('name', '')))

                # 5. Monta a Estrutura do Super Relatório
                report = {
                    "01_metadados": {
                        "internal_id": pol_id,
                        "camara_id": details.get("externalId"),
                        "nome": name,
                        "partido_estado": f"{details.get('party')} - {details.get('state')}",
                        "data_extracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "02_documentos_lidos_e_grafos": {
                        "notas_fiscais_agrupadas": despesas_count,
                        "empresas_qsa_e_contratos_mapeados": empresas_count,
                        "municipios_recebedores_de_emendas": municipios_count,
                        "promessas_campanha_identificadas": promessas_count,
                        "votacoes_analisadas_nlp": votos_count # <--- NOVO
                    },
                    "03_estatisticas_patrimoniais_e_uso_maquina": {
                        "total_gasto_cota_parlamentar": details.get("expenses"), # Removido o default 0 para ver se vem None (falha)
                        "taxa_ausencia_plenario": details.get("absences"),
                        "patrimonio_declarado_2022": details.get("declaredAssets"),
                        "fator_anomalia_patrimonial": details.get("wealthAnomaly")
                    },
                    "04_alertas_de_inteligencia": {
                        "motor_rachadinha_score": details.get("cabinetRiskScore"),
                        "motor_rachadinha_evidencias": safe_json_load(details.get("cabinetRiskDetails")),
                        "anomalias_contratacao_gabinete_qtd": details.get("staffAnomalyCount"),
                        "anomalias_contratacao_gabinete_evidencias": safe_json_load(details.get("staffAnomalyDetails")),
                        "anomalia_espacial_teletransporte_qtd": details.get("teleportAnomalyCount"), # <--- NOVO
                        "anomalia_espacial_evidencias": safe_json_load(details.get("teleportAnomalyDetails")), # <--- NOVO
                        "mencoes_suspeitas_diarios_oficiais": details.get("nlpGazetteCount"),
                        "processos_judiciais_improbidade": details.get("judicialRiskScore")
                    }
                }
                
                # 6. Salva no Disco
                filename = f"super_report_{name.replace(' ', '_').lower()}_{details.get('externalId')}.json"
                filepath = REPORTS_DIR / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=4, ensure_ascii=False)
                    
                logger.info(f"  ✅ Super Relatório de Auditoria gerado: {filename}")
                
        except Exception as e:
            logger.error(f"Erro ao gerar super relatórios: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera o Super Relatório JSON Final")
    parser.add_argument("--limit", type=int, default=15, help="Número de parlamentares para gerar relatório")
    args = parser.parse_args()
    
    worker = SuperReportWorker()
    worker.run(limit=args.limit)