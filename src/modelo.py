"""Modelo epidemiológico SIR estocástico baseado em agentes.

Uma RÉPLICA é uma simulação completa de uma epidemia em uma cidade sintética,
executada com uma semente aleatória própria. A réplica é a UNIDADE DE TRABALHO
do projeto: réplicas não dependem umas das outras, por isso podem ser
distribuídas entre processos sem nenhuma comunicação durante o cálculo.

O modelo (por dia simulado):
  * cada agente infeccioso encontra de `contatos_min` a `contatos_max` pessoas
    sorteadas ao acaso na cidade;
  * se a pessoa encontrada é suscetível, ela se infecta com probabilidade
    `prob_transmissao` (reduzida pela eficácia da vacina, se vacinada);
  * quem se infecta pode precisar de internação, com probabilidade que
    depende da faixa etária; parte dos internados vai a óbito;
  * após `dias_infeccioso` dias o agente se recupera e não transmite mais.

O resultado de interesse para a política pública é se o PICO de internados
ultrapassa o número de leitos da cidade (colapso hospitalar).
"""

import random
from collections import deque

# (nome, fração da população, prob. internação se infectado, letalidade entre internados)
# Frações aproximadas da pirâmide etária brasileira (Censo 2022).
FAIXAS_ETARIAS = (
    ("0-19", 0.27, 0.003, 0.02),
    ("20-59", 0.58, 0.012, 0.08),
    ("60+", 0.15, 0.060, 0.22),
)

PARAMETROS_PADRAO = dict(
    populacao=100_000,       # habitantes da cidade sintética
    leitos_por_100k=200,     # ~2 leitos por 1.000 habitantes (média brasileira)
    infectados_iniciais=20,  # casos importados no dia 0
    prob_transmissao=0.10,   # probabilidade de transmitir em um contato (R0 ~ 2,0)
    contatos_min=2,          # contatos diários por infeccioso (mínimo)
    contatos_max=6,          # contatos diários por infeccioso (máximo)
    dias_infeccioso=5,       # dias em que o agente transmite
    dias_internacao=7,       # dias que um internado ocupa o leito
    eficacia_vacina=0.70,    # redução da probabilidade de infecção
    dias_max=365,            # limite de dias simulados
)


def _cobertura_por_faixa(cobertura, populacao, rng_faixas):
    """Distribui as doses priorizando os idosos, depois adultos, depois jovens.

    Devolve a fração vacinada em cada faixa etária.
    """
    doses = int(cobertura * populacao)
    tamanhos = [sum(1 for f in rng_faixas if f == i) for i in range(len(FAIXAS_ETARIAS))]
    fracao = [0.0] * len(FAIXAS_ETARIAS)
    for i in reversed(range(len(FAIXAS_ETARIAS))):  # 60+ primeiro
        if tamanhos[i] == 0:
            continue
        aplicadas = min(doses, tamanhos[i])
        fracao[i] = aplicadas / tamanhos[i]
        doses -= aplicadas
    return fracao


def simular_replica(cenario, cobertura, indice, semente, parametros=None):
    """Executa uma réplica e devolve um dicionário com os indicadores.

    Determinística: a mesma `semente` produz sempre o mesmo resultado,
    independentemente do processo em que roda.
    """
    p = dict(PARAMETROS_PADRAO)
    if parametros:
        p.update(parametros)

    rng = random.Random(semente)
    n = p["populacao"]
    leitos = p["leitos_por_100k"] * n // 100_000
    prob = p["prob_transmissao"]
    prob_vacinado = prob * (1.0 - p["eficacia_vacina"])
    cmin = p["contatos_min"]
    amplitude = p["contatos_max"] - cmin + 1
    dias_inf = p["dias_infeccioso"]
    dias_uti = p["dias_internacao"]
    dias_max = p["dias_max"]
    prob_intern = [f[2] for f in FAIXAS_ETARIAS]
    letalidade = [f[3] for f in FAIXAS_ETARIAS]

    # --- população sintética -------------------------------------------------
    faixa = rng.choices(range(len(FAIXAS_ETARIAS)), weights=[f[1] for f in FAIXAS_ETARIAS], k=n)
    cob_faixa = _cobertura_por_faixa(cobertura, n, faixa)
    aleatorio = rng.random
    vacinado = bytearray(aleatorio() < cob_faixa[fx] for fx in faixa)

    # 0 = suscetível, 1 = infeccioso, 2 = recuperado
    estado = bytearray(n)

    # --- casos iniciais -------------------------------------------------------
    iniciais = []
    while len(iniciais) < p["infectados_iniciais"]:
        a = int(aleatorio() * n)
        if estado[a] == 0:
            estado[a] = 1
            iniciais.append(a)

    coortes = deque([iniciais])   # coortes[i] = agentes infectados no dia (hoje - i)
    infecciosos = len(iniciais)
    total_infectados = infecciosos
    internados = 0
    altas = [0] * (dias_max + dias_uti + 2)
    total_internacoes = 0
    obitos = 0
    pico_infectados = infecciosos
    dia_pico = 0
    pico_internados = 0
    dia_pico_internados = 0
    dia = 0

    # --- laço principal: um dia por iteração ---------------------------------
    while infecciosos > 0 and dia < dias_max:
        dia += 1
        novos = []
        for coorte in coortes:
            for _agente in coorte:
                for _ in range(cmin + int(aleatorio() * amplitude)):
                    b = int(aleatorio() * n)
                    if estado[b] != 0:
                        continue
                    if aleatorio() < (prob_vacinado if vacinado[b] else prob):
                        estado[b] = 1
                        novos.append(b)
                        if aleatorio() < prob_intern[faixa[b]]:
                            total_internacoes += 1
                            internados += 1
                            altas[dia + dias_uti] += 1
                            if aleatorio() < letalidade[faixa[b]]:
                                obitos += 1

        # recuperação da coorte mais antiga
        if len(coortes) == dias_inf:
            for a in coortes.popleft():
                estado[a] = 2
        coortes.append(novos)
        infecciosos = sum(len(c) for c in coortes)
        total_infectados += len(novos)
        internados -= altas[dia]

        if infecciosos > pico_infectados:
            pico_infectados, dia_pico = infecciosos, dia
        if internados > pico_internados:
            pico_internados, dia_pico_internados = internados, dia

    return {
        "cenario": cenario,
        "cobertura": cobertura,
        "replica": indice,
        "semente": semente,
        "duracao_dias": dia,
        "total_infectados": total_infectados,
        "pico_infectados": pico_infectados,
        "dia_pico": dia_pico,
        "total_internacoes": total_internacoes,
        "pico_internados": pico_internados,
        "dia_pico_internados": dia_pico_internados,
        "obitos": obitos,
        "leitos": leitos,
        "colapso": int(pico_internados > leitos),
    }


if __name__ == "__main__":
    # Execução direta para inspeção rápida do modelo.
    import json
    import sys
    import time

    cobertura = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    t0 = time.perf_counter()
    r = simular_replica("teste", cobertura, 0, 42)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    print(f"tempo: {time.perf_counter() - t0:.2f}s")
