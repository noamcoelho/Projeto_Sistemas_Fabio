#!/bin/bash
# Roteiro completo no Linux (instância na nuvem): teste rápido, corrida, benchmark.
# Uso: ./executar_tudo.sh [perfil=completo] [repeticoes=3]
set -e
cd "$(dirname "$0")"
PERFIL=${1:-completo}
REP=${2:-3}
PY=${PYTHON:-python3}

echo "== 1. Teste de fumaça (perfil rapido)"
$PY src/sequencial.py --perfil rapido --silencioso
$PY src/paralelo.py   --perfil rapido --silencioso
$PY src/verificar.py resultados/sequencial_rapido.json resultados/paralelo_rapido.json

echo; echo "== 2. Condição de corrida: sem trava x com trava"
$PY src/demo_corrida.py --execucoes 3

echo; echo "== 3. Benchmark (perfil $PERFIL, $REP repetições)"
$PY src/benchmark.py --perfil "$PERFIL" --repeticoes "$REP"

echo; echo "Tabela para o relatório: resultados/benchmark_$PERFIL.md"
