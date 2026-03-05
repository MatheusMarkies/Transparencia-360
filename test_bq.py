import os
from google.cloud import bigquery

# Aponta para as suas credenciais
cred_path = os.path.join(os.path.expanduser('~'), '.config', 'gcloud', 'application_default_credentials.json')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path

# Injetando o nome do seu projeto explicitamente
project_id = "tactile-sentry-284814"
client = bigquery.Client(project=project_id)

print("=== COLUNAS DA TABELA SOCIOS ===")
query_socios = f"SELECT column_name FROM `basedosdados.br_me_cnpj.INFORMATION_SCHEMA.COLUMNS` WHERE table_name = 'socios'"
for row in client.query(query_socios):
    print(row.column_name)

print("\n=== COLUNAS DA TABELA EMPRESAS ===")
query_empresas = f"SELECT column_name FROM `basedosdados.br_me_cnpj.INFORMATION_SCHEMA.COLUMNS` WHERE table_name = 'empresas'"
for row in client.query(query_empresas):
    print(row.column_name)