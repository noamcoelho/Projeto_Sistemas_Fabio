"""Versão PARALELA: N processos consomem uma fila de réplicas e somam os
resultados em um estado compartilhado protegido por um Lock.

Por que PROCESSOS e não threads: a simulação é 100% CPU em Python puro
(sorteios e laços). Em CPython o GIL permite que apenas uma thread execute
bytecode por vez, então threads não dariam ganho. Processos têm interpretadores
independentes e ocupam núcleos distintos.

Estratégia:
  * fila dinâmica (multiprocessing.Queue): cada processo pega a próxima
    réplica quando termina a anterior -> equilibra trabalho desigual
    (cobertura 0% custa ~10x mais que cobertura 80%);
  * estado compartilhado (Manager().dict() + Manager().list());
  * seção crítica = `agregar()` + append da réplica, protegida por
    multiprocessing.Lock -- só a soma é serializada, não a simulação.

Uso:
    python src/paralelo.py --perfil demo --processos 8
    python src/paralelo.py --perfil corrida --sem-trava   # SOMENTE para demonstrar a condição de corrida
"""

import argparse
import multiprocessing as mp
import time

from comum import (PERFIS, agregar, caminho_resultado, consolidar, cpus_disponiveis,
                   escrever_resultado, gerar_tarefas, imprimir_tempos, resumo_tabela)
from modelo import simular_replica


def trabalhador(ident, fila, estado, replicas, trava, usar_trava, estatisticas):
    """Laço de um processo trabalhador."""
    t_inicio = time.perf_counter()
    t_simulacao = 0.0
    t_espera_trava = 0.0
    t_secao_critica = 0.0
    concluidas = 0

    while True:
        tarefa = fila.get()
        if tarefa is None:          # sentinela: acabou o trabalho
            break

        # ---- trabalho independente (fora da seção crítica) -----------------
        t0 = time.perf_counter()
        resultado = simular_replica(**tarefa)
        t_simulacao += time.perf_counter() - t0

        # ---- SEÇÃO CRÍTICA -------------------------------------------------
        t0 = time.perf_counter()
        if usar_trava:
            trava.acquire()
        t1 = time.perf_counter()
        t_espera_trava += t1 - t0
        try:
            agregar(estado, resultado)   # leitura-modificação-escrita no estado compartilhado
            replicas.append(resultado)
        finally:
            if usar_trava:
                trava.release()
        t_secao_critica += time.perf_counter() - t1
        # ---- fim da seção crítica -----------------------------------------
        concluidas += 1

    estatisticas.append(dict(
        processo=ident,
        replicas=concluidas,
        tempo_vivo=time.perf_counter() - t_inicio,
        tempo_simulacao=t_simulacao,
        tempo_espera_trava=t_espera_trava,
        tempo_secao_critica=t_secao_critica,
    ))


def executar(perfil, processos, usar_trava=True, saida=None, silencioso=False):
    saida = saida or caminho_resultado(f"paralelo_{perfil}.json")
    t_inicio = time.perf_counter()

    tarefas = gerar_tarefas(perfil)
    with mp.Manager() as gerente:
        estado = gerente.dict()          # estado compartilhado escrito por todos os processos
        replicas = gerente.list()
        estatisticas = gerente.list()
        trava = mp.Lock()                # primitiva que protege a seção crítica
        fila = mp.Queue()
        for tarefa in tarefas:
            fila.put(tarefa)
        for _ in range(processos):
            fila.put(None)

        procs = [
            mp.Process(target=trabalhador, name=f"trabalhador-{i}",
                       args=(i, fila, estado, replicas, trava, usar_trava, estatisticas))
            for i in range(processos)
        ]
        t_preparacao = time.perf_counter() - t_inicio
        if not silencioso:
            print(f"[paralelo] perfil={perfil} tarefas={len(tarefas)} processos={processos} "
                  f"populacao={PERFIS[perfil]['populacao']} trava={'sim' if usar_trava else 'NÃO'}", flush=True)

        t0 = time.perf_counter()
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        t_trabalhadores = time.perf_counter() - t0

        t0 = time.perf_counter()
        final = consolidar(perfil, estado, replicas)
        stats = sorted((dict(s) for s in estatisticas), key=lambda s: s["processo"])
    digest = escrever_resultado(saida, final)
    t_finalizacao = time.perf_counter() - t0
    t_total = time.perf_counter() - t_inicio

    tempos_vivos = [s["tempo_vivo"] for s in stats]
    tempos = dict(
        modo="paralelo", perfil=perfil, processos=processos, tarefas=len(tarefas),
        trava=usar_trava,
        tempo_total=t_total, tempo_preparacao=t_preparacao,
        tempo_trabalhadores=t_trabalhadores, tempo_finalizacao=t_finalizacao,
        soma_tempo_simulacao=sum(s["tempo_simulacao"] for s in stats),
        soma_espera_trava=sum(s["tempo_espera_trava"] for s in stats),
        soma_secao_critica=sum(s["tempo_secao_critica"] for s in stats),
        desbalanceamento=(max(tempos_vivos) - min(tempos_vivos)) / max(tempos_vivos) if tempos_vivos else 0.0,
        replicas_por_processo=[s["replicas"] for s in stats],
        replicas_agregadas=final["total_replicas"],
        sha256=digest, saida=str(saida),
    )
    if not silencioso:
        print(resumo_tabela(final))
        for s in stats:
            print(f"  processo {s['processo']}: {s['replicas']:>4} réplicas | vivo {s['tempo_vivo']:.2f}s | "
                  f"simulando {s['tempo_simulacao']:.2f}s | esperando trava {s['tempo_espera_trava']*1000:.1f}ms | "
                  f"na seção crítica {s['tempo_secao_critica']*1000:.1f}ms")
        print(f"resultado: {saida}\nsha256: {digest}")
        print(f"tempo total: {t_total:.2f}s (trabalhadores {t_trabalhadores:.2f}s, "
              f"preparação {t_preparacao:.2f}s, finalização {t_finalizacao:.2f}s)")
    imprimir_tempos(tempos)
    return tempos


def main():
    ap = argparse.ArgumentParser(description="Simulação paralela de cenários de vacinação")
    ap.add_argument("--perfil", choices=PERFIS, default="demo")
    ap.add_argument("--processos", "-p", type=int, default=cpus_disponiveis())
    ap.add_argument("--saida", default=None)
    ap.add_argument("--sem-trava", action="store_true",
                    help="desliga o Lock (apenas para demonstrar a condição de corrida)")
    ap.add_argument("--silencioso", action="store_true")
    args = ap.parse_args()
    executar(args.perfil, args.processos, usar_trava=not args.sem_trava,
             saida=args.saida, silencioso=args.silencioso)


if __name__ == "__main__":
    mp.freeze_support()
    main()
