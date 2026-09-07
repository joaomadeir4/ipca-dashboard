import json
import sys

import pandas as pd

from gerar_narrativas import buscar_dados, enriquecer, OUTPUT_PATH


FRASES_TENDENCIA = {
    "subiu": [
        lambda ini, fim, de, para: f"Entre {ini} e {fim}, o acumulado em 12 meses subiu de {de} para {para}.",
        lambda ini, fim, de, para: f"No intervalo de {ini} a {fim}, a inflação acumulada em 12 meses avançou de {de} para {para}.",
        lambda ini, fim, de, para: f"De {ini} a {fim}, observa-se uma escalada do acumulado em 12 meses, de {de} para {para}.",
    ],
    "recuou": [
        lambda ini, fim, de, para: f"Entre {ini} e {fim}, o acumulado em 12 meses recuou de {de} para {para}.",
        lambda ini, fim, de, para: f"No intervalo de {ini} a {fim}, a inflação acumulada em 12 meses desacelerou de {de} para {para}.",
        lambda ini, fim, de, para: f"De {ini} a {fim}, houve arrefecimento do acumulado em 12 meses, de {de} para {para}.",
    ],
}

FRASES_PICO = [
    lambda mes, valor: f"O momento de maior pressão foi {mes}, com variação mensal de {valor}.",
    lambda mes, valor: f"O pico de pressão inflacionária no período ocorreu em {mes}, quando a variação mensal chegou a {valor}.",
    lambda mes, valor: f"{mes} concentrou o maior repique do período, com alta mensal de {valor}.",
]

FRASES_MARGEM = [
    lambda pct: f"Em {pct}% dos meses do período, a margem absorvida ficou negativa, indicando que o negócio não repassou integralmente os custos aos preços finais.",
    lambda pct: f"A margem absorvida foi negativa em {pct}% dos meses analisados, sinal de que parte dos custos não chegou a ser repassada ao consumidor.",
    lambda pct: f"Em {pct}% do período, o setor comprimiu margens em vez de repassar integralmente os custos aos preços.",
]


def escolher(lista, seed):
    return lista[seed % len(lista)]


def montar_resumo(df, narrativas, periodo_inicio, periodo_fim):
    recorte = df[(df["periodo"] >= periodo_inicio) & (df["periodo"] <= periodo_fim)]
    if recorte.empty:
        return "Nenhum dado disponível para esse período."

    primeiro = recorte.iloc[0]
    ultimo = recorte.iloc[-1]
    fmt_mes = lambda p: p.strftime("%Y-%m")
    fmt_pct = lambda v: "--" if pd.isna(v) else f"{v:.2f}%"
    seed = len(recorte)

    com_acum = recorte[recorte["variacao_acum_12m"].notna()]
    if len(com_acum) > 1:
        delta = com_acum.iloc[-1]["variacao_acum_12m"] - com_acum.iloc[0]["variacao_acum_12m"]
        direcao = "subiu" if delta >= 0 else "recuou"
        frase = escolher(FRASES_TENDENCIA[direcao], seed)
        trecho_tendencia = frase(
            fmt_mes(primeiro["periodo"]), fmt_mes(ultimo["periodo"]),
            fmt_pct(com_acum.iloc[0]["variacao_acum_12m"]), fmt_pct(com_acum.iloc[-1]["variacao_acum_12m"])
        )
    else:
        trecho_tendencia = f"Em {fmt_mes(primeiro['periodo'])}, a variação mensal foi de {fmt_pct(primeiro['variacao_mensal'])}."

    pico = recorte.loc[recorte["variacao_mensal"].idxmax()]
    trecho_pico = escolher(FRASES_PICO, seed)(fmt_mes(pico["periodo"]), fmt_pct(pico["variacao_mensal"]))

    com_margem = recorte[recorte["margem_absorvida_lag1"].notna()]
    trecho_margem = ""
    if len(com_margem) > 0:
        negativos = (com_margem["margem_absorvida_lag1"] < 0).sum()
        pct = round(negativos / len(com_margem) * 100)
        trecho_margem = escolher(FRASES_MARGEM, seed)(pct)

    chave_pico = fmt_mes(pico["periodo"])
    chave_ultimo = fmt_mes(ultimo["periodo"])
    insight_pico = narrativas.get(chave_pico)
    insight_ultimo = narrativas.get(chave_ultimo)
    if insight_pico and insight_pico != insight_ultimo:
        trecho_detalhe = f"{insight_pico} {insight_ultimo or ''}".strip()
    else:
        trecho_detalhe = insight_ultimo or insight_pico or ""

    return " ".join(t for t in [trecho_tendencia, trecho_pico, trecho_margem, trecho_detalhe] if t)


def main():
    if len(sys.argv) != 3:
        print("uso: python sintetizar_narrativa.py YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)

    periodo_inicio, periodo_fim = pd.to_datetime(sys.argv[1]), pd.to_datetime(sys.argv[2])

    df = enriquecer(buscar_dados())
    narrativas = json.load(open(OUTPUT_PATH, encoding="utf-8"))

    resumo = montar_resumo(df, narrativas, periodo_inicio, periodo_fim)
    print(resumo)
    print(f"\n({len(resumo)} caracteres)")


if __name__ == "__main__":
    main()
