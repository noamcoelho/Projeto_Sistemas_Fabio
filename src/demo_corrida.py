"""Demonstra a condição de corrida na seção crítica e mostra que o Lock a resolve.

Roda a versão paralela várias vezes com a MESMA entrada:
  1) com --sem-trava  -> a soma no estado compartilhado perde atualizações,
                         o resultado muda a cada execução e difere do sequencial;
  2) com o Lock       -> o resultado é estável e idêntico ao sequencial.

O perfil "corrida" usa réplicas minúsculas (1.500 habitantes) e numerosas para
que os processos entrem na seção crítica com muita frequência e a colisão
fique evidente.

Uso:
    python src/demo_corrida.py [--execucoes 3] [--processos 8]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from comum import PASTA_RESULTADOS, cpus_disponiveis

SRC = Path(__file__).resolve().parent


def rodar(script, *extra):
    cmd = [sys.executable, str(SRC / script), "--perfil", "corrida", "--silencioso", *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
    linha = [l for l in proc.stdout.splitlines() if l.startswith("TEMPOS ")][-1]
    tempos = json.loads(linha[len("TEMPOS "):])
    with open(tempos["saida"], encoding="utf-8") as f:
        dados = json.load(f)
    total_infectados = sum(c["somas"]["total_infectados"] for c in dados["cenarios"].values())
    replicas_contadas = sum(c["replicas"] for c in dados["cenarios"].values())
    return tempos["sha256"][:12], replicas_contadas, total_infectados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execucoes", type=int, default=3)
    ap.add_argument("--processos", type=int, default=cpus_disponiveis())
    args = ap.parse_args()
    PASTA_RESULTADOS.mkdir(exist_ok=True)

    print("Referência sequencial (perfil corrida):")
    ref = rodar("sequencial.py", "--saida", str(PASTA_RESULTADOS / "corrida_sequencial.json"))
    print(f"  sha256={ref[0]}  réplicas contadas={ref[1]}  soma de infectados={ref[2]}\n")

    cab = f"{'execução':>8} {'sha256':>12} {'réplicas':>9} {'infectados':>11} {'igual ao seq.?':>15}"
    for rotulo, extra in (("SEM TRAVA (condição de corrida)", ["--sem-trava"]),
                          ("COM TRAVA (multiprocessing.Lock)", [])):
        print(f"Paralelo, {args.processos} processos, {rotulo}:")
        print(cab)
        estaveis = 0
        for i in range(1, args.execucoes + 1):
            saida = PASTA_RESULTADOS / f"corrida_{'sem' if extra else 'com'}_trava_{i}.json"
            r = rodar("paralelo.py", "-p", str(args.processos), "--saida", str(saida), *extra)
            igual = r == ref
            estaveis += igual
            print(f"{i:>8} {r[0]:>12} {r[1]:>9} {r[2]:>11} {'sim' if igual else 'NÃO':>15}")
        print(f"  -> {estaveis}/{args.execucoes} execuções iguais ao sequencial\n")


if __name__ == "__main__":
    main()
