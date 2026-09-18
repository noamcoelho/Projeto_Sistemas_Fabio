"""Mede tempo sequencial e paralelo NA MESMA MÁQUINA e COM A MESMA ENTRADA,
mais de uma vez, e calcula speedup, eficiência e o teto da lei de Amdahl.

Uso:
    python src/benchmark.py --perfil completo --repeticoes 3 --processos 1 2 4 8

Saída: resultados/benchmark_<perfil>.json e resultados/benchmark_<perfil>.md
(a tabela .md vai direto para o relatório).

Lei de Amdahl: S(p) <= 1 / ((1 - f) + f / p), onde f é a fração do tempo
sequencial que pode ser paralelizada. Aqui f é ESTIMADA a partir da própria
versão sequencial: f = tempo_simulacao / tempo_total (a preparação e a
escrita do resultado são inerentemente sequenciais).
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from comum import PASTA_RESULTADOS, cpus_disponiveis

SRC = Path(__file__).resolve().parent


def rodar(script, perfil, *extra):
    cmd = [sys.executable, str(SRC / script), "--perfil", perfil, "--silencioso", *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
    linha = [l for l in proc.stdout.splitlines() if l.startswith("TEMPOS ")][-1]
    return json.loads(linha[len("TEMPOS "):])


def amdahl(f, p):
    return 1.0 / ((1.0 - f) + f / p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default="demo")
    ap.add_argument("--repeticoes", type=int, default=3)
    ap.add_argument("--processos", type=int, nargs="+", default=None,
                    help="quantidades de processos a testar (padrão: 1 2 4 ... até nº de CPUs)")
    args = ap.parse_args()

    ncpu = cpus_disponiveis()
    lista_p = args.processos or sorted({1, 2, 4, 8, 16, ncpu} & set(range(1, ncpu + 1)))
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    saida_seq = PASTA_RESULTADOS / f"bench_sequencial_{args.perfil}.json"

    print(f"máquina: {platform.node()} | {platform.platform()} | {ncpu} CPUs lógicas | Python {platform.python_version()}")
    print(f"perfil={args.perfil} repetições={args.repeticoes} processos={lista_p}\n")

    # ---- sequencial ---------------------------------------------------------
    seq = []
    for i in range(args.repeticoes):
        t = rodar("sequencial.py", args.perfil, "--saida", str(saida_seq))
        seq.append(t)
        print(f"sequencial #{i+1}: {t['tempo_total']:.2f}s  (sha256 {t['sha256'][:12]})", flush=True)
    hash_ref = seq[0]["sha256"]
    t_seq = statistics.median(t["tempo_total"] for t in seq)
    f_estimada = statistics.median(t["tempo_simulacao"] / t["tempo_total"] for t in seq)
    print(f"  mediana sequencial: {t_seq:.2f}s | fração paralelizável estimada f = {f_estimada:.4f}\n")

    # ---- paralelo -----------------------------------------------------------
    linhas = []
    for p in lista_p:
        execs = []
        for i in range(args.repeticoes):
            saida = PASTA_RESULTADOS / f"bench_paralelo_{args.perfil}_p{p}.json"
            t = rodar("paralelo.py", args.perfil, "-p", str(p), "--saida", str(saida))
            execs.append(t)
            ok = "ok" if t["sha256"] == hash_ref else "DIFERENTE!"
            print(f"paralelo p={p} #{i+1}: {t['tempo_total']:.2f}s  (sha256 {t['sha256'][:12]} {ok})", flush=True)
        t_par = statistics.median(t["tempo_total"] for t in execs)
        linha = dict(
            processos=p,
            tempo_paralelo=t_par,
            tempos=[t["tempo_total"] for t in execs],
            speedup=t_seq / t_par,
            eficiencia=t_seq / t_par / p,
            amdahl_teto=amdahl(f_estimada, p),
            preparacao=statistics.median(t["tempo_preparacao"] for t in execs),
            finalizacao=statistics.median(t["tempo_finalizacao"] for t in execs),
            espera_trava_total=statistics.median(t["soma_espera_trava"] for t in execs),
            secao_critica_total=statistics.median(t["soma_secao_critica"] for t in execs),
            desbalanceamento=statistics.median(t["desbalanceamento"] for t in execs),
            resultado_identico=all(t["sha256"] == hash_ref for t in execs),
        )
        linhas.append(linha)
        print(f"  mediana p={p}: {t_par:.2f}s | speedup {linha['speedup']:.2f}x | "
              f"teto Amdahl {linha['amdahl_teto']:.2f}x | eficiência {linha['eficiencia']*100:.0f}%\n", flush=True)

    resumo = dict(
        maquina=platform.node(), plataforma=platform.platform(), cpus_logicas=ncpu,
        python=platform.python_version(), data=time.strftime("%Y-%m-%d %H:%M:%S"),
        perfil=args.perfil, repeticoes=args.repeticoes, tarefas=seq[0]["tarefas"],
        tempo_sequencial=t_seq, tempos_sequenciais=[t["tempo_total"] for t in seq],
        fracao_paralelizavel=f_estimada, sha256=hash_ref, paralelo=linhas,
    )
    caminho_json = PASTA_RESULTADOS / f"benchmark_{args.perfil}.json"
    with open(caminho_json, "w", encoding="utf-8") as fp:
        json.dump(resumo, fp, indent=1, ensure_ascii=False)

    md = [
        f"### Benchmark — perfil `{args.perfil}` ({seq[0]['tarefas']} réplicas)",
        "",
        f"- Máquina: `{platform.node()}` — {platform.platform()} — {ncpu} CPUs lógicas — Python {platform.python_version()}",
        f"- Data: {resumo['data']}",
        f"- Tempo sequencial (mediana de {args.repeticoes}): **{t_seq:.2f} s** — execuções: "
        + ", ".join(f"{x:.2f}" for x in resumo["tempos_sequenciais"]),
        f"- Fração paralelizável estimada: **f = {f_estimada:.4f}**",
        f"- SHA-256 do resultado: `{hash_ref[:16]}…` (idêntico em todas as execuções: "
        f"{'sim' if all(l['resultado_identico'] for l in linhas) else 'NÃO'})",
        "",
        "| Processos | Tempo paralelo (s) | Speedup medido | Teto de Amdahl | Eficiência | Espera na trava (s) | Desbalanceamento |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for l in linhas:
        md.append(f"| {l['processos']} | {l['tempo_paralelo']:.2f} | {l['speedup']:.2f}x | "
                  f"{l['amdahl_teto']:.2f}x | {l['eficiencia']*100:.0f}% | "
                  f"{l['espera_trava_total']:.3f} | {l['desbalanceamento']*100:.0f}% |")
    md.append("")
    md.append("Speedup = T_sequencial / T_paralelo (medianas, mesma máquina, mesma entrada). "
              "Teto de Amdahl = 1 / ((1 − f) + f / p). Espera na trava = soma, em todos os processos, "
              "do tempo bloqueado no `Lock.acquire()`. Desbalanceamento = (maior − menor tempo de vida "
              "dos processos) / maior.")
    caminho_md = PASTA_RESULTADOS / f"benchmark_{args.perfil}.md"
    caminho_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nsalvo em {caminho_json} e {caminho_md}")


if __name__ == "__main__":
    main()
