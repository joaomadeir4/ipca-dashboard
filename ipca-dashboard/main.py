import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google.cloud import bigquery
from google.oauth2 import service_account
from pydantic import BaseModel
import anthropic

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI()
credentials_info = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON"))
credentials = service_account.Credentials.from_service_account_info(credentials_info)
client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="southamerica-east1")

TABLE = "port-joaomadeira.projeto_inflacao.ipca_alimentacao_fora_domicilio"

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


class DadoPeriodo(BaseModel):
    periodo: str
    variacao_mensal: float | None = None
    variacao_acum_12m: float | None = None
    margem_absorvida_lag1: float | None = None


class NarrativaRequest(BaseModel):
    periodo_inicio: str
    periodo_fim: str
    dados: list[DadoPeriodo]


@app.get("/dados")
def get_dados():
    query = f"SELECT * FROM `{TABLE}`"
    rows = client.query(query).result()
    return [dict(row) for row in rows]


@app.post("/narrativa")
def gerar_narrativa(req: NarrativaRequest):
    linhas = "\n".join(
        f"{d.periodo}: variação mensal {d.variacao_mensal}%, "
        f"acumulado 12m {d.variacao_acum_12m}%, "
        f"margem absorvida lag1 {d.margem_absorvida_lag1}%"
        for d in req.dados
    )

    prompt = (
        f"Você é um analista econômico. Abaixo estão dados mensais do IPCA "
        f"de alimentação fora do domicílio no Brasil, entre {req.periodo_inicio} "
        f"e {req.periodo_fim}:\n\n{linhas}\n\n"
        "Escreva uma narrativa analítica em português, de 3 a 4 frases, explicando "
        "o comportamento da inflação nesse período. Cite eventos econômicos reais "
        "quando relevante (ex: pandemia, crise cambial, políticas de juros)."
    )

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    narrativa = next(
        block.text for block in response.content if block.type == "text"
    )

    return {"narrativa": narrativa}


@app.get("/")
def read_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
