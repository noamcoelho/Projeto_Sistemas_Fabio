# Roteiro da apresentação (10 min) + arguição

Regra do professor: **tudo ao vivo** (nada gravado, nada em captura de tela), tempo máximo
12 min. Cada integrante apresenta uma parte e responde na arguição sobre uma parte que **não**
apresentou — então todos precisam dominar todas as partes. As falas de cada um estão em
[roteiro_4_integrantes.md](roteiro_4_integrantes.md).

## Preparação (antes de entrar na sala)

- [ ] Notebook da apresentação carregado, na tomada, plano de energia em "Desempenho máximo"
      (o speedup cai se o processador estiver economizando energia).
- [ ] Fechar navegador, antivírus em varredura, atualizações — nada competindo pela CPU.
- [ ] `python src/sequencial.py --perfil rapido` já rodado uma vez (aquece o cache de bytecode).
- [ ] `resultados/benchmark_completo.md` já gerado **nesta mesma máquina** com 3 repetições
      (a medição de minutos não cabe nos 3 min de execução; ao vivo rodamos o perfil `demo`).
- [ ] Terminal aberto na pasta do projeto, fonte grande (Ctrl + = três vezes).
- [ ] Editor aberto em `src/comum.py` (função `agregar`) e `src/paralelo.py` (função `trabalhador`).
- [ ] Repositório e PDF publicados no ambiente virtual.

## Parte 1 — O problema e por que ele se divide (2,5 min) — _integrante 1_

Na tela: `README.md` (tabela de cenários) e `src/modelo.py`.

- A pergunta: qual cobertura vacinal evita colapso dos leitos (2 por 1.000 hab.)?
- Modelo SIR estocástico baseado em agentes; 200 mil agentes com faixa etária; vacina prioriza idosos.
- **Entrada:** 500 tarefas (5 coberturas × 100 sementes). **Unidade de trabalho:** uma réplica,
  `simular_replica()`. **Volume:** ~0,4 s por réplica → minutos sequencial.
- Réplicas são independentes → paralelizável. O que é compartilhado é só a soma final.
- Resultado verificável: sementes fixas → JSON idêntico byte a byte (SHA-256).

## Parte 2 — A seção crítica (2,5 min) — _integrante 2_

Na tela: `agregar()` em `src/comum.py` e o bloco `acquire/try/finally/release` em `src/paralelo.py`.

- Mostrar a linha `estado[chave] = estado.get(chave, 0) + valor`: ler → somar → escrever.
- Primitiva: `multiprocessing.Lock`, só em torno da agregação, não da simulação.
- **Rodar ao vivo:** `python src/demo_corrida.py --execucoes 3` (~20 s).
  Apontar: sem trava, réplicas contadas ≠ 600 e SHA muda; com trava, 3/3 iguais ao sequencial.
- Por que processos e não threads: GIL; trabalho é 100 % CPU.

## Parte 3 — A execução (3 min) — _integrante 3_

No terminal, na pasta do projeto:

```bash
python src/sequencial.py --perfil demo            # ~45 s, mostra progresso e tempo
python src/paralelo.py   --perfil demo -p 8       # ~7 s, mostra tempo por processo
python src/verificar.py resultados/sequencial_demo.json resultados/paralelo_demo.json
```

Enquanto o sequencial roda, comentar a tabela de resultados que aparece (P(colapso) por cobertura).
Ao final do paralelo, apontar: tempo por processo, espera na trava em ms, SHA-256 igual.

## Parte 4 — O ganho (2 min) — _integrante 4_

Na tela: `resultados/benchmark_completo.md` (gerado nesta máquina, 3 repetições).

- Speedup medido vs. teto de Amdahl (f = 0,9996 → teto ≈ p).
- Onde foi a diferença, em ordem de importância: queda de frequência com todos os núcleos
  ativos (turbo boost), hyper-threading se houver, desbalanceamento no fim da fila, custo de
  IPC do Manager e criação de processos, espera na trava (ms — desprezível).

---

# Perguntas prováveis na arguição (e respostas curtas)

**Problema**
- *Por que Monte Carlo?* O modelo é estocástico; uma execução é uma amostra. Precisamos de
  muitas para estimar a probabilidade de colapso.
- *Como garante que a paralela dá o mesmo resultado?* Semente por réplica (`SEMENTE_BASE + índice`),
  somas de inteiros (ordem não importa), lista ordenada antes de gravar, JSON com chaves ordenadas.
- *O que é R0 aqui?* ≈ prob. transmissão × contatos médios × dias infeccioso = 0,10 × 4 × 5 = 2,0.

**Seção crítica**
- *O que exatamente é a condição de corrida?* Dois processos leem o mesmo valor antigo do
  contador, cada um soma o seu e escreve; a escrita do segundo apaga a do primeiro.
- *Por que não travar o laço inteiro?* Seria correto, mas serializaria a simulação: speedup 1×.
- *Lock vs. semáforo vs. monitor?* `Lock` é um semáforo binário; usamos porque só um processo
  deve agregar por vez. Um `Semaphore(k)` permitiria k; um monitor (`Condition`) serviria para
  esperar por uma condição, que não precisamos.
- *O Manager já não é seguro?* Cada operação isolada (`get`, `__setitem__`) é atômica no gerente,
  mas a sequência ler-somar-escrever não é — por isso a trava.
- *Por que processos e não threads?* GIL do CPython: uma thread por vez executando bytecode;
  trabalho é CPU pura. Threads serviriam para E/S.

**Execução**
- *Por que o perfil `demo` e não o `completo` ao vivo?* O completo leva minutos; o demo tem a
  mesma estrutura (5 cenários) com menos réplicas e cabe nos 3 min. O benchmark do completo foi
  medido nesta mesma máquina antes.
- *Como vocês sabem que a paralela não está "errando rápido"?* `verificar.py` compara o SHA-256
  do JSON inteiro com o da versão sequencial.
- *O que é a fila?* `multiprocessing.Queue`: cada processo retira a próxima réplica quando
  termina a anterior; sentinela `None` avisa que acabou.

**Medição / ganho**
- *O que é a lei de Amdahl?* S(p) = 1 / ((1 − f) + f/p): mesmo com infinitos processadores, a
  parte sequencial (1 − f) limita o ganho a 1/(1 − f).
- *Como estimou f?* Na versão sequencial: tempo de simulação / tempo total = 0,9996.
- *Por que 8 processos não dão 8×?* Frequência do processador cai com todos os núcleos ativos;
  desbalanceamento no fim da fila; custo de criar processos e de IPC; hyper-threading se a
  máquina tiver menos núcleos físicos que lógicos.
- *Por que 2 e 4 processos deram um pouco mais que 2× e 4×?* Diferença de 2–4 %, dentro do ruído
  de medição (o sequencial oscilou 42,5–44,0 s). Não é ganho real; por isso repetimos e usamos mediana.
- *Por que medir mais de uma vez e usar mediana?* Ruído do sistema; mediana ignora outliers.
- *Eficiência?* speedup / p. Cai conforme p sobe pelos motivos acima.
- *E se a máquina tivesse 16 núcleos?* Ganho até o número de núcleos físicos; depois só o
  overhead cresce.
