import os
import json
import time

from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import anthropic

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TABLE = "port-joaomadeira.projeto_inflacao.ipca_alimentacao_fora_domicilio"
OUTPUT_PATH = os.path.join(BASE_DIR, "static", "narrativas.json")
RATE_LIMIT_SECONDS = 0.5

credentials_info = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON"))
credentials = service_account.Credentials.from_service_account_info(credentials_info)
bq_client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="southamerica-east1")

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def buscar_dados():
    query = f"SELECT * FROM `{TABLE}` ORDER BY periodo ASC"
    rows = bq_client.query(query).result()
    return [dict(row) for row in rows]


def gerar_insight(row):
    periodo = row["periodo"].strftime("%Y-%m")
    prompt = (
        f"Dados do IPCA de alimentação fora do domicílio no Brasil para {periodo}:\n"
        f"variação mensal: {row['variacao_mensal']}%\n"
        f"acumulado 12 meses: {row['variacao_acum_12m']}%\n"
        f"margem absorvida (lag 1m): {row['margem_absorvida_lag1']}%\n\n"
        "Escreva um insight analítico em português sobre esse mês específico, "
        "considerando o contexto econômico do período. Sem introdução, direto ao ponto, "
        "máximo 2 frases."
    )

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}],
    )

    texto = next(block.text for block in response.content if block.type == "text")
    return periodo, texto.strip()


def main():
    dados = buscar_dados()
    narrativas = {}

    for i, row in enumerate(dados):
        periodo, insight = gerar_insight(row)
        narrativas[periodo] = insight
        print(f"[{i + 1}/{len(dados)}] {periodo}: OK")
        time.sleep(RATE_LIMIT_SECONDS)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(narrativas, f, ensure_ascii=False, indent=2)

    print(f"\nSalvo em {OUTPUT_PATH} ({len(narrativas)} períodos)")


if __name__ == "__main__":
    main()
