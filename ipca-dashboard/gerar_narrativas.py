import os
import json
import time

import pandas as pd
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
    df = pd.DataFrame([dict(row) for row in rows])
    df["periodo"] = pd.to_datetime(df["periodo"])
    return df


def enriquecer(df):
    df = df.copy()
    df["media_movel_3m"] = df["variacao_mensal"].rolling(3).mean()
    df["percentil_historico"] = df["variacao_mensal"].rank(pct=True) * 100
    df["var_mesmo_mes_ano_anterior"] = df["variacao_mensal"].shift(12)
    return df


def gerar_insight(row):
    periodo = row["periodo"].strftime("%Y-%m")

    contexto_extra = []
    if pd.notna(row["media_movel_3m"]):
        contexto_extra.append(f"média móvel de 3 meses: {row['media_movel_3m']:.2f}%")
    if pd.notna(row["percentil_historico"]):
        contexto_extra.append(f"percentil histórico da variação mensal: {row['percentil_historico']:.0f}")
    if pd.notna(row["var_mesmo_mes_ano_anterior"]):
        contexto_extra.append(f"variação mensal no mesmo mês do ano anterior: {row['var_mesmo_mes_ano_anterior']:.2f}%")
    contexto_extra_str = "\n".join(contexto_extra)

    prompt = (
        f"Dados do IPCA de alimentação fora do domicílio no Brasil para {periodo}:\n"
        f"variação mensal: {row['variacao_mensal']}%\n"
        f"acumulado 12 meses: {row['variacao_acum_12m']}%\n"
        f"margem absorvida (lag 1m): {row['margem_absorvida_lag1']}%\n"
        f"{contexto_extra_str}\n\n"
        "margem_absorvida_lag1: diferença entre variacao_mensal e repasse_lag1. "
        "Valor POSITIVO significa que o custo do mês foi maior que o repasse (negócio absorveu a diferença, "
        "margem comprimida). Valor NEGATIVO significa que o repasse foi maior que o custo (negócio repassou "
        "mais do que o custo subiu, margem dilatada).\n\n"
        "Escreva um insight analítico em português sobre esse mês específico, "
        "considerando o contexto econômico do período e, quando relevante, como esse mês se compara "
        "à tendência recente e ao histórico da série. Sem introdução, direto ao ponto, máximo 2 frases."
    )

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}],
    )

    texto = next(block.text for block in response.content if block.type == "text")
    return periodo, texto.strip()


def main():
    df = enriquecer(buscar_dados())
    narrativas = {}

    for i, row in df.iterrows():
        periodo, insight = gerar_insight(row)
        narrativas[periodo] = insight
        print(f"[{i + 1}/{len(df)}] {periodo}: OK")
        time.sleep(RATE_LIMIT_SECONDS)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(narrativas, f, ensure_ascii=False, indent=2)

    print(f"\nSalvo em {OUTPUT_PATH} ({len(narrativas)} períodos)")


if __name__ == "__main__":
    main()
