# Roteiro completo no Windows: teste rápido, demonstração da corrida, benchmark.
# Uso: .\executar_tudo.ps1 [-Perfil demo] [-Repeticoes 3]
param(
    [string]$Perfil = "demo",
    [int]$Repeticoes = 3
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1. Teste de fumaça (perfil rapido)" -ForegroundColor Cyan
python src\sequencial.py --perfil rapido --silencioso
python src\paralelo.py   --perfil rapido --silencioso
python src\verificar.py resultados\sequencial_rapido.json resultados\paralelo_rapido.json

Write-Host "`n== 2. Condição de corrida: sem trava x com trava" -ForegroundColor Cyan
python src\demo_corrida.py --execucoes 3

Write-Host "`n== 3. Benchmark (perfil $Perfil, $Repeticoes repetições)" -ForegroundColor Cyan
python src\benchmark.py --perfil $Perfil --repeticoes $Repeticoes

Write-Host "`nTabela para o relatório: resultados\benchmark_$Perfil.md" -ForegroundColor Green
