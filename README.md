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

## Dashboard (`static/index.html`)

Layout construído seguindo princípios de storytelling com dados (Cole Nussbaumer): hierarquia visual clara, cor usada só para guiar o olho, sem "chartjunk".

Ordem das seções:
1. **KPIs**: variação mensal atual, acumulado 12m, repasse (lag 1m), margem absorvida (lag 1m)
2. **Narrativa do período**: seletor De/Até e botão que chama `POST /narrativa` e exibe o texto gerado
3. **Acumulado em 12 meses**: gráfico de linha com área
4. **Variação mensal**: gráfico de barras (azul = positivo, vermelho = negativo), com linha de base no zero
5. **Custo x repasse**: gráfico de barras mostrando quando o custo superou o repasse (vermelho) ou o repasse superou o custo (roxo), com linha tracejada no zero
6. **Sazonalidade**: heatmap de 12 células (jan-dez) com intensidade de azul proporcional à média histórica de variação mensal

## Versão estática (`static/snapshot_artifact.html`)

Publicada como [Claude Artifact](https://claude.ai/code/artifacts) para compartilhamento sem precisar rodar o backend. O projeto original usa IA generativa em tempo real via API da Anthropic para gerar narrativas sob demanda, para qualquer intervalo de meses (ver `POST /narrativa` acima). Por questão de custo de API, essa versão pública é um exemplo estático que simula esse comportamento:

- **Dados congelados**: snapshot da tabela BigQuery embutido diretamente no HTML, sem fetch.
- **Insights mensais pré-gerados**: `gerar_narrativas.py` roda uma vez, gera um insight curto por mês via API (mesmo modelo, `claude-sonnet-5`) e salva em `static/narrativas.json`, embutido no HTML.
- **Consolidação real via `sample`**: ao selecionar um intervalo e clicar em "Gerar narrativa", a capability `sample` do runtime de Artifacts recebe os insights mensais daquele intervalo e produz, ao vivo, um parágrafo coerente cobrindo o período inteiro — a consolidação acontece a cada clique, não é texto fixo. Isso evita expor uma chave de API no HTML público, e o uso é debitado da conta claude.ai de quem está vendo a página, não do dono do projeto.

**Limitação conhecida**: artifacts que declaram a capability `sample` não podem ser compartilhados publicamente pela plataforma Claude — o compartilhamento fica restrito à organização/workspace de quem publicou. Essa versão não serve, hoje, para um link público de portfólio; o repositório e o dashboard local continuam sendo a referência para demonstrar o projeto a terceiros.

## Notas de arquitetura

- O client do BigQuery usa `location="southamerica-east1"` porque o dataset (`projeto_inflacao`) está nessa região. Omitir isso causa erro 404 "dataset not found".
- O endpoint `/narrativa` busca o primeiro bloco do tipo `text` na resposta da Anthropic (`next(b for b in response.content if b.type == "text")`), em vez de assumir `content[0]`, porque respostas mais longas podem vir precedidas de um bloco de `thinking`.
