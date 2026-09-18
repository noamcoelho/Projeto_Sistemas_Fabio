# Roteiro da apresentação (10 min) + arguição

Regra do professor: **tudo ao vivo** (nada gravado, nada em captura de tela), console da
nuvem aberto, tempo máximo 12 min. Cada integrante apresenta uma parte e responde na arguição
sobre uma parte que **não** apresentou — então todos precisam dominar todas as partes.

## Preparação (antes de entrar na sala)

- [ ] Instância criada e rodando (`terraform apply` ~1 h antes; conferir `http://IP:8080/saude`).
- [ ] Terminal SSH aberto na instância, dentro de `~/projeto`, com `nproc` já executado.
- [ ] Console AWS aberto na aba EC2 → Instâncias, e outra aba em Grupos de segurança.
- [ ] `resultados/benchmark_completo.md` já gerado na instância (a medição de minutos não cabe
      nos 3 min de execução; ao vivo rodamos o perfil `demo`).
- [ ] Repositório e PDF publicados no ambiente virtual.
- [ ] Editor aberto em `src/comum.py` (função `agregar`) e `src/paralelo.py` (função `trabalhador`).

## Parte 1 — O problema e por que ele se divide (2 min) — _integrante A_

Na tela: `README.md` (tabela de cenários) e `src/modelo.py`.

- A pergunta: qual cobertura vacinal evita colapso dos leitos (2 por 1.000 hab.)?
- Modelo SIR estocástico baseado em agentes; 200 mil agentes com faixa etária; vacina prioriza idosos.
- **Entrada:** 500 tarefas (5 coberturas × 100 sementes). **Unidade de trabalho:** uma réplica,
  `simular_replica()`. **Volume:** ~0,4 s por réplica → minutos sequencial.
- Réplicas são independentes → paralelizável. O que é compartilhado é só a soma final.
- Resultado verificável: sementes fixas → JSON idêntico byte a byte (SHA-256).

## Parte 2 — A seção crítica (2 min) — _integrante B_

Na tela: `agregar()` em `src/comum.py` e o bloco `acquire/try/finally/release` em `src/paralelo.py`.

- Mostrar a linha `estado[chave] = estado.get(chave, 0) + valor`: ler → somar → escrever.
- Primitiva: `multiprocessing.Lock`, só em torno da agregação, não da simulação.
- **Rodar ao vivo:** `python3 src/demo_corrida.py --execucoes 3` (~20 s).
  Apontar: sem trava, réplicas contadas ≠ 600 e SHA muda; com trava, 3/3 iguais ao sequencial.
- Por que processos e não threads: GIL; trabalho é 100 % CPU.

## Parte 3 — Os recursos na nuvem (2 min) — _integrante C_

Na tela: console AWS ao vivo.

- EC2 → Instâncias: `sd-vacinacao`, *running*, `c6i.2xlarge`, zona `sa-east-1a`, região São Paulo.
- Explicar o tipo: 8 vCPUs = 4 núcleos físicos × 2 (hyper-threading) — vai voltar na parte 5.
- Grupo de segurança `sd-vacinacao-sg` → Regras de entrada:
  22/TCP origem `IP-da-equipe/32` (administrativa, restrita); 8080/TCP origem `0.0.0.0/0` (serviço).
- Mostrar `nuvem/terraform/main.tf` com a validação que recusa 0.0.0.0/0 na porta 22.
- Navegador em `http://IP:8080/` — o serviço responde de fora.

## Parte 4 — A execução (3 min) — _integrante D_

No terminal SSH da instância:

```bash
python3 src/sequencial.py --perfil demo            # ~45 s, mostra progresso e tempo
python3 src/paralelo.py   --perfil demo -p 8       # ~8-12 s, mostra tempo por processo
python3 src/verificar.py resultados/sequencial_demo.json resultados/paralelo_demo.json
```

Enquanto o sequencial roda, comentar a tabela de resultados que aparece (P(colapso) por cobertura).
Ao final do paralelo, apontar: tempo por processo, espera na trava em ms, SHA-256 igual.

## Parte 5 — O ganho (1 min) — _integrante A ou B_

Na tela: `resultados/benchmark_completo.md` (gerado na instância, 3 repetições).

- Speedup medido vs. teto de Amdahl (f = 0,9996 → teto ≈ p).
- Onde foi a diferença, em ordem de importância: hyper-threading (4 → 8 quase não escala),
  desbalanceamento no fim da fila, custo de IPC do Manager e criação de processos,
  espera na trava (ms — desprezível).

## Encerrar

`terraform destroy` depois da aula (ou deixar para o professor ver que a instância existe e
destruir em seguida).

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

**Nuvem**
- *Por que essa região?* São Paulo: menor latência para nós e requisito de mostrar ao vivo.
- *Por que `c6i.2xlarge`?* Família otimizada para CPU, 8 vCPUs para testar 1/2/4/8 processos.
- *O que aconteceria se a porta 22 estivesse aberta para 0.0.0.0/0?* Qualquer pessoa na
  internet poderia tentar autenticar por SSH (força bruta); critério zerado. Nossa validação impede.
- *Como a aplicação chegou à instância?* `user_data` (script `setup_instancia.sh`) instala
  Python, clona o repositório, roda teste de fumaça e sobe o serviço via systemd.

**Medição / ganho**
- *O que é a lei de Amdahl?* S(p) = 1 / ((1 − f) + f/p): mesmo com infinitos processadores, a
  parte sequencial (1 − f) limita o ganho a 1/(1 − f).
- *Como estimou f?* Na versão sequencial: tempo de simulação / tempo total = 0,9996.
- *Por que 8 processos não dão 8×?* Hyper-threading: 4 núcleos físicos; desbalanceamento no fim
  da fila; custo de criar processos e de IPC.
- *Por que medir mais de uma vez e usar mediana?* Ruído do sistema; mediana ignora outliers.
- *Eficiência?* speedup / p. Cai conforme p sobe pelos motivos acima.
- *E se a instância tivesse 16 vCPUs?* Ganho até ~8 núcleos físicos; depois só o overhead cresce.
