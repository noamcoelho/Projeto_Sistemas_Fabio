"""Versão SEQUENCIAL: um único processo executa todas as réplicas, uma após a outra.

Uso:
    python src/sequencial.py --perfil demo
"""

import argparse
import time

from comum import (PERFIS, agregar, caminho_resultado, consolidar, escrever_resultado,
                   gerar_tarefas, imprimir_tempos, novo_estado, resumo_tabela)
from modelo import simular_replica


def main():
    ap = argparse.ArgumentParser(description="Simulação sequencial de cenários de vacinação")
    ap.add_argument("--perfil", choices=PERFIS, default="demo")
    ap.add_argument("--saida", default=None, help="arquivo JSON de saída")
    ap.add_argument("--silencioso", action="store_true")
    args = ap.parse_args()
    saida = args.saida or caminho_resultado(f"sequencial_{args.perfil}.json")

    t_inicio = time.perf_counter()
    tarefas = gerar_tarefas(args.perfil)
    estado = novo_estado()
    replicas = []
    t_preparacao = time.perf_counter() - t_inicio

    if not args.silencioso:
        print(f"[sequencial] perfil={args.perfil} tarefas={len(tarefas)} "
              f"populacao={PERFIS[args.perfil]['populacao']}", flush=True)

    t0 = time.perf_counter()
    for i, tarefa in enumerate(tarefas, 1):
        resultado = simular_replica(**tarefa)
        agregar(estado, resultado)      # sem concorrência: não precisa de lock
        replicas.append(resultado)
        if not args.silencioso and i % 25 == 0:
            print(f"  {i}/{len(tarefas)} réplicas ({time.perf_counter() - t0:.1f}s)", flush=True)
    t_simulacao = time.perf_counter() - t0

    t0 = time.perf_counter()
    final = consolidar(args.perfil, estado, replicas)
    digest = escrever_resultado(saida, final)
    t_finalizacao = time.perf_counter() - t0
    t_total = time.perf_counter() - t_inicio

    if not args.silencioso:
        print(resumo_tabela(final))
        print(f"resultado: {saida}\nsha256: {digest}")
        print(f"tempo total: {t_total:.2f}s (simulação {t_simulacao:.2f}s)")
    imprimir_tempos(dict(
        modo="sequencial", perfil=args.perfil, processos=1, tarefas=len(tarefas),
        tempo_total=t_total, tempo_preparacao=t_preparacao,
        tempo_simulacao=t_simulacao, tempo_finalizacao=t_finalizacao,
        sha256=digest, saida=str(saida),
    ))


if __name__ == "__main__":
    main()
