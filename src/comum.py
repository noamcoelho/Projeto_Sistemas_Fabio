"""Código compartilhado pelas versões sequencial e paralela.

Aqui ficam: os perfis de execução (tamanho da entrada), a geração da lista de
tarefas, a AGREGAÇÃO dos resultados no estado compartilhado (o trecho que a
versão paralela protege com lock) e a escrita determinística do resultado.
"""

import hashlib
import json
import os
from pathlib import Path

PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_RESULTADOS = PASTA_RAIZ / "resultados"

COBERTURAS_PADRAO = (0.0, 0.2, 0.4, 0.6, 0.8)

# Perfis: definem o VOLUME da entrada.
#   corrida  -> réplicas minúsculas e muito numerosas: exercita a seção crítica
#               milhares de vezes; usado pelo demo_corrida.py
#   rapido   -> teste de fumaça (segundos)
#   demo     -> apresentação ao vivo (~1 min sequencial)
#   completo -> medição para o relatório (minutos sequencial)
PERFIS = {
    "corrida": dict(populacao=1_500, replicas=120, coberturas=COBERTURAS_PADRAO),
    "rapido": dict(populacao=10_000, replicas=4, coberturas=(0.0, 0.4, 0.8)),
    "demo": dict(populacao=100_000, replicas=50, coberturas=COBERTURAS_PADRAO),
    "completo": dict(populacao=200_000, replicas=100, coberturas=COBERTURAS_PADRAO),
}

SEMENTE_BASE = 20260921

# Campos somados por cenário no estado compartilhado.
CAMPOS_SOMADOS = (
    "total_infectados",
    "pico_infectados",
    "total_internacoes",
    "pico_internados",
    "obitos",
    "duracao_dias",
    "colapso",
)
LARGURA_FAIXA_HISTOGRAMA = 50  # leitos


def nome_cenario(cobertura):
    return f"cobertura_{int(round(cobertura * 100)):03d}"


def gerar_tarefas(perfil, semente_base=SEMENTE_BASE):
    """Lista de tarefas independentes. A ordem intercala cenários para que
    trabalho pesado (cobertura baixa) e leve (cobertura alta) se misturem."""
    cfg = PERFIS[perfil]
    parametros = {"populacao": cfg["populacao"]}
    tarefas = []
    indice = 0
    for replica in range(cfg["replicas"]):
        for cobertura in cfg["coberturas"]:
            tarefas.append(dict(
                cenario=nome_cenario(cobertura),
                cobertura=cobertura,
                indice=indice,
                semente=semente_base + indice,
                parametros=parametros,
            ))
            indice += 1
    return tarefas


def novo_estado():
    return {}


def agregar(estado, resultado):
    """SEÇÃO CRÍTICA (na versão paralela).

    Soma os indicadores de UMA réplica no estado compartilhado. Cada linha é
    uma leitura-modificação-escrita (`estado[c] = estado.get(c) + v`): se dois
    processos executarem isto ao mesmo tempo sem exclusão mútua, um sobrescreve
    a soma do outro e atualizações se perdem.

    `estado` pode ser um dict comum (sequencial) ou um Manager().dict()
    (paralelo) -- a interface é a mesma.
    """
    c = resultado["cenario"]
    estado[f"{c}|replicas"] = estado.get(f"{c}|replicas", 0) + 1
    for campo in CAMPOS_SOMADOS:
        chave = f"{c}|{campo}"
        estado[chave] = estado.get(chave, 0) + resultado[campo]
    faixa = (resultado["pico_internados"] // LARGURA_FAIXA_HISTOGRAMA) * LARGURA_FAIXA_HISTOGRAMA
    chave = f"{c}|hist|{faixa:05d}"
    estado[chave] = estado.get(chave, 0) + 1


def consolidar(perfil, estado, replicas):
    """Monta o resultado final (determinístico) a partir do estado agregado."""
    cfg = PERFIS[perfil]
    estado = dict(estado)
    cenarios = {}
    for cobertura in cfg["coberturas"]:
        c = nome_cenario(cobertura)
        n = estado.get(f"{c}|replicas", 0)
        somas = {campo: estado.get(f"{c}|{campo}", 0) for campo in CAMPOS_SOMADOS}
        medias = {campo: (somas[campo] / n if n else None) for campo in CAMPOS_SOMADOS}
        hist = {k.split("|")[-1]: v for k, v in estado.items() if k.startswith(f"{c}|hist|")}
        cenarios[c] = dict(
            cobertura=cobertura,
            replicas=n,
            somas=somas,
            medias=medias,
            probabilidade_colapso=(somas["colapso"] / n if n else None),
            histograma_pico_internados=dict(sorted(hist.items())),
        )
    replicas = sorted((dict(r) for r in replicas), key=lambda r: r["replica"])
    return dict(
        perfil=perfil,
        populacao=cfg["populacao"],
        replicas_por_cenario=cfg["replicas"],
        total_replicas=len(replicas),
        cenarios=cenarios,
        replicas=replicas,
    )


def escrever_resultado(caminho, resultado):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        json.dump(resultado, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return hash_arquivo(caminho)


def hash_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def resumo_tabela(resultado):
    """Tabela legível com a resposta à pergunta de saúde pública."""
    linhas = [
        f"População: {resultado['populacao']:,} | réplicas por cenário: {resultado['replicas_por_cenario']}".replace(",", "."),
        f"{'cobertura':>10} {'infectados':>12} {'internações':>12} {'pico leitos':>12} {'óbitos':>8} {'P(colapso)':>11}",
    ]
    for c in resultado["cenarios"].values():
        m = c["medias"]
        if c["replicas"] == 0:
            continue
        linhas.append(
            f"{c['cobertura']*100:>9.0f}% {m['total_infectados']:>12.0f} {m['total_internacoes']:>12.0f} "
            f"{m['pico_internados']:>12.0f} {m['obitos']:>8.0f} {c['probabilidade_colapso']:>11.2f}"
        )
    return "\n".join(linhas)


def imprimir_tempos(tempos):
    """Última linha da saída: JSON com os tempos, lido pelo benchmark.py."""
    print("TEMPOS " + json.dumps(tempos, ensure_ascii=False), flush=True)


def caminho_resultado(nome):
    return PASTA_RESULTADOS / nome


def cpus_disponiveis():
    return os.cpu_count() or 1
