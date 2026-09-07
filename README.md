# IPCA Dashboard

Dashboard de inflação de alimentação fora do domicílio (IPCA), com dados do BigQuery e narrativas analíticas geradas por IA.

## Stack

- **Fonte de dados**: API IBGE/SIDRA
- **ETL**: Google Colab + Pandas
- **Data warehouse**: Google BigQuery (`google-cloud-bigquery`)
- **Backend**: FastAPI + uvicorn
- **IA**: Anthropic API (`anthropic`), modelo `claude-sonnet-5`
- **Frontend**: HTML/CSS/JS puro + Chart.js via CDN (sem frameworks)

## Estrutura

```
inflacao/
├── etl_ingestao_inflacao.ipynb  # notebook completo do pipeline (ingestão + tratamento + carga)
└── ipca-dashboard/
    ├── main.py                      # API FastAPI
    ├── gerar_narrativas.py          # script que pré-gera os insights mensais (static/narrativas.json)
    ├── requirements.txt
    ├── .env                         # ANTHROPIC_API_KEY, GOOGLE_CREDENTIALS_JSON (não versionado)
    └── static/
        ├── index.html                # dashboard completo (consome a API local)
        ├── narrativas.json           # insight mensal pré-gerado (usado pelo artifact estático)
        └── snapshot_artifact.html    # versão standalone publicada como Claude Artifact
```

## Endpoints

### `GET /`
Serve o dashboard (`static/index.html`).

### `GET /dados`
Consulta a tabela `port-joaomadeira.projeto_inflacao.ipca_alimentacao_fora_domicilio` no BigQuery e retorna todos os registros como JSON.

Campos por registro: `periodo`, `variacao_mensal`, `variacao_acum_12m`, `margem_absorvida_lag1`, `margem_absorvida_lag2`, `repasse_lag1`, `repasse_lag2`, `subgrupo`, `indice`, `ano`, `mes`.

### `POST /narrativa`
Gera uma narrativa analítica em português para um intervalo de períodos, usando a API da Anthropic.

**Request body:**
```json
{
  "periodo_inicio": "2021-04-01",
  "periodo_fim": "2021-10-01",
  "dados": [
    {
      "periodo": "2021-04-01",
      "variacao_mensal": 0.23,
      "variacao_acum_12m": 4.68,
      "margem_absorvida_lag1": -0.66
    }
  ]
}
```

**Response:**
```json
{ "narrativa": "Entre abril e outubro de 2021, a inflação..." }
```

## Pipeline de dados

Detalhes completos em `etl_ingestao_inflacao.ipynb`. Resumo:

1. **Ingestão**: dados extraídos da API IBGE/SIDRA (Colab)
2. **Tratamento**: limpeza e cálculo de métricas derivadas (Pandas)
3. **Carga**: gravação no BigQuery
4. **Serving**: API deste projeto expõe os dados (`GET /dados`) e a narrativa (`POST /narrativa`)

## Setup

### 1. Credenciais BigQuery

Crie uma service account no Console GCP com os papéis **BigQuery Data Viewer** e **BigQuery Job User** e baixe a chave JSON. O `main.py` lê essa credencial de uma variável de ambiente, não de um arquivo no disco.

### 2. Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto (`ipca-dashboard/`):

```
ANTHROPIC_API_KEY=sua-chave-aqui
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key":"...", ...}
```

`GOOGLE_CREDENTIALS_JSON` é o conteúdo inteiro do arquivo JSON da service account, em uma única linha. No deploy (ex: Render), configure essa mesma variável no painel do serviço — nunca commite o arquivo JSON.

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Rodar

```bash
python main.py
```

ou, com reload automático:

```bash
uvicorn main:app --reload
```

Acesse `http://localhost:8000`.

## Frontend: dois arquivos, duas finalidades

O projeto tem dois HTMLs em `static/`, com propósitos diferentes — não são "versões" um do outro.

### `index.html` — dashboard operacional

Consome o backend FastAPI local (`main.py`):
- `GET /dados` busca dados em tempo real do BigQuery
- `POST /narrativa` gera narrativa via API Anthropic sob demanda, para qualquer intervalo selecionado
- Requer o servidor rodando e as credenciais configuradas (`.env`)
- Uso: desenvolvimento local e deploy no Render

Layout segue storytelling com dados (Cole Nussbaumer): KPIs no topo, depois narrativa do período, acumulado 12m, variação mensal, custo x repasse e sazonalidade — hierarquia visual clara, cor só pra guiar o olho, sem "chartjunk".

### `snapshot_artifact.html` — demonstração pública

Arquivo standalone, sem dependência de backend:
- Dados embutidos como `const DATA = [...]` — snapshot de jul/2026
- Insights mensais pré-gerados via API Anthropic, embutidos como `const NARRATIVAS = {...}` (175 entradas, uma por mês, geradas por `gerar_narrativas.py`)
- Ao selecionar um período, o JS filtra os insights do intervalo e monta um resumo localmente (tendência, mês de maior pressão, comportamento da margem, mais um insight real do período) — tudo calculado no navegador, sem chamada de API
- Finalidade: página estática para portfólio pessoal, demonstrando o comportamento do projeto sem expor credenciais nem depender do backend

## Notas de arquitetura

- O client do BigQuery usa `location="southamerica-east1"` porque o dataset (`projeto_inflacao`) está nessa região. Omitir isso causa erro 404 "dataset not found".
- O endpoint `/narrativa` busca o primeiro bloco do tipo `text` na resposta da Anthropic (`next(b for b in response.content if b.type == "text")`), em vez de assumir `content[0]`, porque respostas mais longas podem vir precedidas de um bloco de `thinking`.
