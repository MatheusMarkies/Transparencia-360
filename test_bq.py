import os, json, warnings
warnings.filterwarnings('ignore')

# Carrega credenciais direto do arquivo
cred_path = os.path.join(os.path.expanduser('~'), '.config', 'gcloud', 'application_default_credentials.json')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path

from google.cloud import bigquery
client = bigquery.Client(project='tactile-sentry-284814')

sql = "SELECT cnpj_basico, razao_social FROM basedosdados.br_me_cnpj.empresas LIMIT 3"
rows = client.query(sql).result()
for r in rows:
    print(r.cnpj_basico, r.razao_social)

print('\nFuncionou! BigQuery pronto para uso.')
