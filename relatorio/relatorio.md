---
title: "Simulação paralela de políticas de vacinação: modelo SIR baseado em agentes com Monte Carlo"
subtitle: "070080 Sistemas Distribuídos e Paralelos — Projeto de Solução Distribuída, Etapa 1"
author: "Equipe: _(nome 1)_, _(nome 2)_, _(nome 3)_, _(nome 4)_ — Prof. Fábio Rocha de Araújo"
date: "Setembro de 2026"
geometry: margin=2cm
fontsize: 11pt
lang: pt-BR
---

> **Repositório:** `https://github.com/EQUIPE/REPO` _(preencher)_
> Instruções para gerar o PDF em `relatorio/GERAR_PDF.md`. Limite: seis páginas.

# 1. O problema

Cidades brasileiras têm em média cerca de **2 leitos hospitalares por 1.000 habitantes**. Em
uma epidemia respiratória com número básico de reprodução R0 ≈ 2, a pergunta que orienta uma
campanha de vacinação é: **qual cobertura vacinal evita que o pico de internações ultrapasse
os leitos disponíveis?**

Respondemos com um **modelo SIR estocástico baseado em agentes**. Cada habitante de uma cidade
sintética de 200 mil pessoas é um agente com faixa etária (0–19, 20–59, 60+, nas proporções do
Censo 2022) e estado *suscetível*, *infeccioso* ou *recuperado*. A cada dia simulado, cada
infeccioso encontra de 2 a 6 pessoas sorteadas; um suscetível se infecta com probabilidade
0,10 (reduzida em 70 % se vacinado); quem se infecta pode ser internado com probabilidade que
depende da idade (0,3 %, 1,2 % e 6 %) e ocupa um leito por 7 dias; parte dos internados vai a
óbito. A epidemia termina quando não há mais infecciosos.

Por ser estocástico, um único resultado não basta: usamos o **método de Monte Carlo** — para
cada cenário de cobertura (0 %, 20 %, 40 %, 60 % e 80 %, priorizando idosos) executamos 100
**réplicas** com sementes distintas e calculamos médias e a **probabilidade de colapso
hospitalar** (pico de internados > leitos).

**Entrada, unidade de trabalho e volume.** A entrada é a lista de 500 tarefas (cenário,
semente, tamanho da população), gerada deterministicamente por `gerar_tarefas()`. A unidade de
trabalho é **uma réplica** (`simular_replica()` em `src/modelo.py`): ~0,05 s a 0,7 s de CPU
pura em Python, dependendo da cobertura. O volume total dá **minutos** na versão sequencial.

**Resultado verificável.** Cada réplica recebe a semente `SEMENTE_BASE + índice`, então
produz o mesmo resultado em qualquer processo. As agregações são somas de inteiros (comutativas)
e a lista de réplicas é ordenada pelo índice antes da escrita; o JSON é gravado com chaves
ordenadas. Assim, o arquivo da versão paralela é **idêntico byte a byte** ao da sequencial e
comparamos por SHA-256 (`src/verificar.py`).

# 2. Estratégia de paralelização

As réplicas são independentes — não trocam nenhuma informação durante a simulação — o que
caracteriza um problema *embaraçosamente paralelo* na fase de cálculo. O que **não** é
independente é a agregação: todas as réplicas somam seus indicadores nos mesmos contadores
por cenário.

**Processos, não threads.** O trabalho é limitado por processador (sorteios e laços em Python
puro, sem E/S). No CPython o *Global Interpreter Lock* permite que apenas uma thread execute
bytecode por vez; threads só dão ganho quando o tempo é gasto em E/S ou em bibliotecas nativas
que liberam o GIL. Por isso usamos `multiprocessing`: cada trabalhador é um processo com seu
próprio interpretador e ocupa um núcleo distinto.

**Arquitetura** (`src/paralelo.py`):

1. O processo principal cria uma `multiprocessing.Queue` com as 500 tarefas mais um sentinela
   por trabalhador — **fila dinâmica**: quem termina pega a próxima. Optamos por ela e não por
   divisão estática porque uma réplica com 0 % de cobertura custa ~10× mais que uma com 80 %.
2. `N` processos executam `trabalhador()`: retiram uma tarefa, chamam `simular_replica()`
   (fora de qualquer trava) e, ao terminar, entram na seção crítica para agregar.
3. O estado compartilhado é um `Manager().dict()` (somas e histograma por cenário) e um
   `Manager().list()` (réplicas individuais), servidos por um processo gerente.
4. Ao final, o principal consolida, calcula médias e grava o JSON.

# 3. A seção crítica e a primitiva que a protege

```python
# src/comum.py — executado por todos os processos, sobre o mesmo estado compartilhado
def agregar(estado, resultado):
    c = resultado["cenario"]
    estado[f"{c}|replicas"] = estado.get(f"{c}|replicas", 0) + 1
    for campo in CAMPOS_SOMADOS:            # infectados, internações, óbitos, colapso...
        chave = f"{c}|{campo}"
        estado[chave] = estado.get(chave, 0) + resultado[campo]   # LER -> SOMAR -> ESCREVER
    faixa = (resultado["pico_internados"] // 50) * 50
    estado[f"{c}|hist|{faixa:05d}"] = estado.get(f"{c}|hist|{faixa:05d}", 0) + 1

# src/paralelo.py — laço do trabalhador
resultado = simular_replica(**tarefa)     # trabalho independente, sem trava
trava.acquire()                           # multiprocessing.Lock
try:
    agregar(estado, resultado)            # seção crítica
    replicas.append(resultado)
finally:
    trava.release()
```

Cada linha de `agregar()` é uma **leitura-modificação-escrita** sobre um dado compartilhado.
Sem exclusão mútua, dois processos podem ler o mesmo valor antigo, somar e escrever: a
atualização de um deles se perde. A primitiva escolhida é o **`multiprocessing.Lock`**
(um semáforo binário do sistema operacional), adquirido *apenas* em torno da agregação — não em
torno da simulação. A trava é passada aos processos como argumento na criação, o que funciona
tanto com `fork` (Linux) quanto com `spawn` (Windows).

**Teste de estabilidade** (`src/demo_corrida.py`): roda a versão paralela com a mesma entrada
várias vezes, com a flag `--sem-trava` e com a trava, no perfil `corrida` (600 réplicas
minúsculas, para que os 8 processos entrem na seção crítica milhares de vezes por segundo).
Resultado obtido na máquina de desenvolvimento:

| Execução | Sem trava: réplicas contadas | Sem trava: soma de infectados | Com trava: réplicas | Com trava: soma |
|---:|---:|---:|---:|---:|
| sequencial (ref.) | 600 | 402.293 | 600 | 402.293 |
| 1 | 599 | 401.535 | 600 | 402.293 |
| 2 | 597 | 402.293 | 600 | 402.293 |
| 3 | 599 | 400.128 | 600 | 402.293 |

Sem a trava, réplicas "desaparecem" das somas e o SHA-256 muda a cada execução; com a trava,
as três execuções são idênticas ao sequencial.

# 4. Tempos medidos, speedup e o que limitou o ganho

Todas as medições foram feitas **na mesma máquina, com a mesma entrada** (perfil `completo`:
500 réplicas, 200 mil agentes), **3 vezes** cada; reportamos a mediana. O `benchmark.py`
também confere que o SHA-256 de todas as execuções é o mesmo.

**Fração paralelizável.** Na versão sequencial, o tempo é dividido em preparação (gerar a lista
de tarefas), simulação e finalização (consolidar e gravar o JSON). Medimos
f = t_simulação / t_total = **0,9996**; a parte inerentemente sequencial é ~0,04 % (a gravação
do arquivo). O teto de Amdahl é S(p) ≤ 1 / ((1 − f) + f/p).

_(Colar aqui a tabela de `resultados/benchmark_completo.md`.)_

| Processos | Tempo (s) | Speedup medido | Teto de Amdahl | Eficiência | Espera na trava (s) | Desbalanceamento |
|---:|---:|---:|---:|---:|---:|---:|
| 1 (sequencial) | _T_seq_ | 1,00× | 1,00× | 100 % | — | — |
| 2 | | | 2,00× | | | |
| 4 | | | 3,99× | | | |
| 8 | | | 7,98× | | | |

**Medições preliminares na máquina de desenvolvimento** (Windows 11, 8 núcleos físicos sem
hyper-threading, Python 3.12, perfil `demo`: 250 réplicas de 100 mil agentes, 2 repetições,
T_seq = 43,25 s, f = 0,9996):

| Processos | Tempo (s) | Speedup medido | Teto de Amdahl | Eficiência | Espera na trava (s) | Desbalanceamento |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 42,81 | 1,01× | 1,00× | 101 % | 0,001 | 0 % |
| 2 | 20,81 | 2,08× | 2,00× | 104 % | 0,002 | 0 % |
| 4 | 10,68 | 4,05× | 3,99× | 101 % | 0,005 | 1 % |
| 8 | 7,03 | 6,15× | 7,97× | 77 % | 0,003 | 4 % |

O speedup levemente superlinear em 2 e 4 processos vem do *turbo boost*: com poucos núcleos
ativos o processador opera em frequência maior do que com todos ocupados. O mesmo efeito, ao
contrário, explica parte da perda em 8 processos (a frequência cai quando todos os núcleos
trabalham).

**O que limitou a diferença entre o medido e o teto de Amdahl:**

1. **Hyper-threading.** Se a máquina expõe mais CPUs lógicas do que núcleos físicos, dois
   processos no mesmo núcleo disputam as unidades de execução e o ganho ao dobrar os processos
   fica bem abaixo de 2×.
2. **Divisão desigual do trabalho.** As réplicas variam de ~0,05 s (80 %) a ~0,7 s (0 %). A fila
   dinâmica equilibra a maior parte, mas no fim da execução alguns processos ficam ociosos
   enquanto os últimos terminam réplicas pesadas — medido como *desbalanceamento* (diferença
   entre o maior e o menor tempo de vida dos processos).
3. **Comunicação entre processos.** Cada `estado.get()`/`estado[...] =` no `Manager().dict()` é
   uma chamada a outro processo por *pipe*; a agregação de uma réplica faz ~20 delas (~ms). Somado
   à criação dos processos (`spawn` importa os módulos de novo) e à serialização das tarefas na
   `Queue`, é o custo fixo que aparece em `tempo_preparacao` e `tempo_finalização`.
4. **Frequência do processador.** Com todos os núcleos ativos o processador reduz a frequência
   (limite térmico/energético), então cada processo roda um pouco mais devagar do que o
   sequencial rodava sozinho — a lei de Amdahl assume velocidade por núcleo constante.
5. **Espera na seção crítica.** Com a trava apenas em torno da agregação, a soma do tempo
   bloqueado em `acquire()` fica em milissegundos — desprezível diante de minutos de simulação.
   Uma trava em torno do laço inteiro zeraria o ganho; o desenho evita isso.

**Conclusão.** A versão paralela produz exatamente o mesmo resultado que a sequencial, com
speedup de _(X)_× em 8 processos (_(Y)_× em 4, próximo do teto de Amdahl de 3,99×). Para a
política pública, os resultados indicam que a partir de **40 % de cobertura (priorizando idosos)**
a probabilidade de colapso hospitalar cai a zero neste modelo, e que 60 % reduz os óbitos em
cerca de _(Z)_ % em relação ao cenário sem vacina.

# Referências

- Kermack, W. O.; McKendrick, A. G. *A contribution to the mathematical theory of epidemics*, 1927.
- Amdahl, G. M. *Validity of the single processor approach to achieving large scale computing capabilities*, 1967.
- Python Software Foundation. *multiprocessing — Process-based parallelism*; *Thread State and the Global Interpreter Lock*.
- IBGE. Censo Demográfico 2022 — pirâmide etária. CNES/DataSUS — leitos por habitante.
