# Simulação paralela de políticas de vacinação

**Disciplina:** 070080 Sistemas Distribuídos e Paralelos — Projeto de Solução Distribuída, Etapa 1
**Professor:** Fábio Rocha de Araújo
**Equipe:** _(preencher nomes)_

## O problema

Uma cidade de 100–200 mil habitantes tem cerca de 2 leitos por 1.000 habitantes. Diante de
uma epidemia respiratória (R0 ≈ 2), **qual cobertura vacinal evita que o pico de
internações ultrapasse os leitos disponíveis?**

Respondemos com um **modelo SIR estocástico baseado em agentes** (cada habitante é um
agente com faixa etária e estado suscetível/infeccioso/recuperado) executado pelo **método
de Monte Carlo**: para cada cenário de cobertura (0 %, 20 %, 40 %, 60 %, 80 %, priorizando
idosos) simulamos dezenas de epidemias com sementes diferentes e agregamos infectados,
internações, óbitos e a **probabilidade de colapso hospitalar**.

| Cobertura | Infectados | Pico de internados | Óbitos | P(colapso) |
|---:|---:|---:|---:|---:|
| 0 % | ~80 % da população | ~3× os leitos | alto | 1,00 |
| 40 % | ~45 % | ~0,65× os leitos | médio | 0,00 |
| 80 % | < 1 % | ~0 | ~0 | 0,00 |

(valores típicos — os exatos saem em `resultados/*.json`)

## Por que se divide

- **Unidade de trabalho:** uma réplica (uma epidemia completa com uma semente própria).
- **Independência:** réplicas não trocam nenhuma informação durante o cálculo.
- **Volume:** perfil `completo` = 5 cenários × 100 réplicas × 200 mil agentes → minutos na
  versão sequencial.
- **Verificação:** sementes fixas tornam cada réplica determinística; o JSON final é
  idêntico byte a byte (SHA-256) entre a versão sequencial e a paralela.

## Estratégia de paralelização

`multiprocessing` com **processos** (não threads): a simulação é 100 % CPU em Python
puro e o GIL do CPython impede que threads executem bytecode ao mesmo tempo.

1. O processo principal coloca as réplicas em uma `multiprocessing.Queue` (fila dinâmica —
   uma réplica com 0 % de cobertura custa ~10× mais que uma com 80 %, e a fila equilibra isso).
2. `N` processos trabalhadores retiram réplicas da fila e simulam.
3. Ao terminar cada réplica, o trabalhador entra na **seção crítica**: soma os
   indicadores no estado compartilhado (`Manager().dict()`) e anexa a réplica a uma
   lista compartilhada. Isso é uma leitura-modificação-escrita, protegida por
   **`multiprocessing.Lock`** — veja `agregar()` em [src/comum.py](src/comum.py) e
   `trabalhador()` em [src/paralelo.py](src/paralelo.py).
4. O processo principal consolida e grava o resultado.

Só a soma é serializada; a simulação (99,9 % do tempo) roda em paralelo.

## Como executar

Requer apenas Python ≥ 3.10 (biblioteca padrão; sem dependências).

```bash
python src/sequencial.py --perfil demo            # ~45 s em um núcleo moderno
python src/paralelo.py   --perfil demo -p 8       # mesmos resultados, N processos
python src/verificar.py resultados/sequencial_demo.json resultados/paralelo_demo.json

python src/demo_corrida.py                        # mostra a condição de corrida sem o Lock
python src/benchmark.py --perfil completo --repeticoes 3 --processos 1 2 4 8
python src/servidor.py --porta 8080               # serviço HTTP com os resultados
```

Perfis (`src/comum.py`): `rapido` (teste, segundos), `corrida` (seção crítica sob estresse),
`demo` (apresentação, ~45 s sequencial), `completo` (relatório, minutos).

No Windows: `executar_tudo.ps1`; no Linux/instância: `executar_tudo.sh`.

## Estrutura

```
src/modelo.py        modelo SIR baseado em agentes — simular_replica() é a unidade de trabalho
src/comum.py         perfis, geração de tarefas, agregar() [seção crítica], escrita determinística
src/sequencial.py    versão sequencial
src/paralelo.py      versão paralela (Queue + Manager + Lock)
src/demo_corrida.py  prova da condição de corrida e da correção com o Lock
src/verificar.py     compara dois resultados (SHA-256 + diferenças)
src/benchmark.py     tempos, speedup, eficiência e teto de Amdahl -> resultados/benchmark_*.md
src/servidor.py      serviço HTTP na porta 8080
nuvem/               Terraform + AWS CLI + script de inicialização da instância
relatorio/           relatório técnico (Markdown -> PDF)
apresentacao/        roteiro dos 10 minutos e perguntas de arguição
resultados/          saídas (JSON/MD) — geradas, não versionadas
```

## Nuvem

AWS `sa-east-1` (São Paulo), zona `sa-east-1a`, `c6i.2xlarge` (8 vCPUs). Grupo de segurança:
porta 22 restrita ao IP da equipe, porta 8080 aberta. Detalhes em [nuvem/README.md](nuvem/README.md).
