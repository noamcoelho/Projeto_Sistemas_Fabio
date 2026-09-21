# Roteiro por integrante — falas, telas e comandos

Quatro pessoas, 10 minutos, execução ao vivo no notebook da equipe. Cada bloco abaixo é o
que **um** integrante faz e diz; a troca de apresentador é a troca de tela. Decorem a ordem,
não o texto: o professor avalia se o conteúdo aparece, não a leitura.

Quem opera o notebook durante toda a apresentação: **integrante 3** (evita troca de lugar).
Os outros falam ao lado e pedem "abre o arquivo X" / "roda o comando Y".

| Quem | Parte | Tempo | O que aparece na tela |
|---|---|---|---|
| Integrante 1 | O problema e por que ele se divide | 0:00 – 2:30 | `README.md`, `src/modelo.py` |
| Integrante 2 | A seção crítica | 2:30 – 5:00 | `src/comum.py`, `src/paralelo.py`, `demo_corrida.py` rodando |
| Integrante 3 | A execução | 5:00 – 8:00 | terminal: sequencial, paralelo, verificar |
| Integrante 4 | O ganho | 8:00 – 10:00 | `resultados/benchmark_completo.md` |

---

## Integrante 1 — O problema e por que ele se divide (2,5 min)

**Tela 1:** `README.md`, seção "O problema" (tabela de cenários).

> "Boa noite. Nosso problema vem da saúde pública. Uma cidade brasileira típica tem cerca de
> dois leitos hospitalares para cada mil habitantes. Quando chega uma epidemia respiratória —
> como gripe ou COVID, com R0 perto de 2 — a pergunta que o gestor precisa responder é:
> **qual cobertura vacinal evita que o pico de internações ultrapasse os leitos que existem?**"

> "Respondemos com um modelo SIR estocástico baseado em agentes. Cada um dos 200 mil habitantes
> da nossa cidade sintética é um agente com faixa etária — jovem, adulto, idoso, nas proporções
> do Censo 2022 — e um estado: suscetível, infeccioso ou recuperado."

**Tela 2:** `src/modelo.py`, laço principal `while infecciosos > 0` (apontar com o cursor).

> "A cada dia simulado, cada infeccioso encontra de 2 a 6 pessoas ao acaso. Se a pessoa é
> suscetível, ela se infecta com 10 % de chance — 3 % se estiver vacinada. Quem se infecta pode
> ser internado, com probabilidade que depende da idade: 0,3 % nos jovens, 6 % nos idosos. O
> leito fica ocupado sete dias. A vacina é distribuída priorizando os idosos, como numa campanha
> real."

> "Como o modelo é sorteado, uma execução só é uma amostra. Por isso usamos Monte Carlo: para
> cada cobertura — 0, 20, 40, 60 e 80 por cento — rodamos 100 epidemias com sementes
> diferentes e tiramos a média e a probabilidade de colapso."

**Tela 3:** `src/comum.py`, função `gerar_tarefas` e dicionário `PERFIS`.

> "Então aqui está o que o professor pediu: a **entrada** é essa lista de 500 tarefas — cinco
> coberturas vezes cem sementes. A **unidade de trabalho** é uma réplica: uma epidemia inteira,
> a função `simular_replica`. Cada uma leva de 0,05 a 0,7 segundo de CPU pura em Python — as
> sem vacina são as mais pesadas, porque mais gente se infecta. O **volume** total dá minutos
> na versão sequencial."

> "E por que isso se divide? Porque uma réplica não precisa de nada de outra réplica. A única
> coisa compartilhada é a soma no final. E como cada réplica tem sua semente fixa, o resultado
> é determinístico: o arquivo da versão paralela sai idêntico byte a byte ao da sequencial, e
> nós provamos isso com SHA-256. O(a) [nome do integrante 2] mostra agora onde os processos se
> encontram."

---

## Integrante 2 — A seção crítica (2,5 min)

**Tela 1:** `src/comum.py`, função `agregar` (deixar só ela visível).

> "Quando um processo termina uma réplica, ele precisa somar os números dela — infectados,
> internações, óbitos, se houve colapso — nos contadores do cenário. Esses contadores ficam num
> dicionário compartilhado entre todos os processos, um `Manager().dict()`."

> "Olhem esta linha: `estado[chave] = estado.get(chave, 0) + valor`. São três passos: **ler**
> o valor atual, **somar**, **escrever** de volta. Se dois processos fazem isso ao mesmo tempo,
> os dois leem o mesmo valor antigo, cada um soma o seu e escreve — e a soma de um deles se
> perde. Essa é a condição de corrida. Esta função inteira é a nossa seção crítica."

**Tela 2:** `src/paralelo.py`, função `trabalhador`, bloco `trava.acquire()` … `trava.release()`.

> "A primitiva que protege é um `multiprocessing.Lock` — um semáforo binário do sistema
> operacional. Reparem **onde** ele está: só em volta do `agregar` e do `append`. A simulação,
> que é 99,9 % do tempo, roda fora da trava. Se a trava envolvesse o laço inteiro o programa
> estaria correto, mas seria sequencial."

> "E por que processos e não threads? Porque o trabalho é só CPU — sorteio e laço em Python
> puro. No CPython o GIL deixa uma thread por vez executar bytecode; threads não dariam ganho
> nenhum. Cada processo tem seu interpretador e ocupa um núcleo."

**Tela 3:** terminal. Pedir: "roda o demo da corrida".

```bash
python src/demo_corrida.py --execucoes 3
```

(~20 s. Enquanto roda:)

> "Este teste roda a versão paralela três vezes com a mesma entrada, primeiro **sem** a trava —
> tem uma flag só para isso — e depois **com** a trava. Usa réplicas minúsculas e numerosas
> para os oito processos baterem na seção crítica milhares de vezes."

(Quando aparecer a saída, apontar:)

> "Sem trava: eram 600 réplicas, contou 599, 597… a soma de infectados muda a cada execução e
> o hash é diferente todas as vezes. Com trava: 600, 600, 600, mesma soma, mesmo hash do
> sequencial, três de três. Resultado estável. Agora o(a) [nome do integrante 3] roda o
> programa de verdade."

---

## Integrante 3 — A execução (3 min)

Você está no teclado desde o começo. Fonte grande no terminal.

**Comando 1:**

```bash
python src/sequencial.py --perfil demo
```

> "Primeiro a versão sequencial: um processo, 250 réplicas de 100 mil agentes — o perfil de
> demonstração, que cabe no tempo; o benchmark completo, com 500 réplicas de 200 mil, foi medido
> antes nesta mesma máquina e o(a) [integrante 4] mostra já já."

(Leva ~45 s. Enquanto a contagem `25/250, 50/250…` sobe, comentar o problema:)

> "Vai aparecer uma tabela com a resposta da saúde pública. Reparem na coluna P(colapso):
> sem vacina é 1,00 — em todas as réplicas o pico de internados passa dos leitos, chega a três
> vezes a capacidade. Com 40 % de cobertura priorizando idosos a probabilidade já cai a zero, e
> com 60 % os óbitos caem para cerca de um terço."

(Quando terminar, apontar a última linha: `tempo total: 43,xx s` e o `sha256`.)

**Comando 2:**

```bash
python src/paralelo.py --perfil demo -p 8
```

> "Agora a mesma entrada com oito processos."

(~7 s. Apontar na saída:)

> "A mesma tabela, número por número. Embaixo, um resumo por processo: quantas réplicas cada
> um pegou da fila — não é igual, porque a fila é dinâmica e as réplicas têm custo diferente —,
> quanto tempo simulando, e o tempo esperando a trava: alguns **milissegundos** em 7 segundos.
> A seção crítica quase não pesa. Tempo total: 7 segundos contra 43."

**Comando 3:**

```bash
python src/verificar.py resultados/sequencial_demo.json resultados/paralelo_demo.json
```

> "E a prova: os dois arquivos têm o mesmo SHA-256, idênticos byte a byte. A versão paralela
> não está errando rápido — está acertando rápido. O(a) [integrante 4] fecha com o ganho."

Se sobrar tempo: `python src/paralelo.py --perfil demo -p 4` (~11 s) para mostrar a escala.

---

## Integrante 4 — O ganho (2 min)

**Tela:** `resultados/benchmark_completo.md` (gerado nesta máquina, com 3 repetições).

> "O `benchmark.py` roda sequencial e paralelo três vezes cada, na mesma máquina, com a mesma
> entrada, e usa a mediana. Também confere que o SHA-256 saiu igual em todas as execuções."

> "Speedup é tempo sequencial sobre tempo paralelo. Com 2 processos deu [X]×, com 4 deu [Y]×,
> com 8 deu [Z]×." _(preencher com a tabela)_

> "Comparamos com a lei de Amdahl: S de p é 1 sobre (1 − f) mais f sobre p, onde f é a fração
> paralelizável. Medimos f na própria versão sequencial: tempo de simulação sobre tempo total,
> 0,9996 — só a escrita do JSON é inerentemente sequencial. Então o teto é praticamente p:
> 2, 4, 8."

> "Em 2 e 4 processos batemos no teto. Em 8 ficamos em [Z]×, [E] % de eficiência. O que limitou,
> em ordem de importância:"

> "**Um**, frequência: com todos os núcleos ocupados o processador baixa o clock — a lei de
> Amdahl assume que cada núcleo mantém a velocidade, e não mantém. **Dois**, divisão desigual:
> a réplica sem vacina custa dez vezes mais que a com 80 %; a fila dinâmica equilibra quase
> tudo, mas no final alguns processos ficam parados esperando o último terminar — está na coluna
> desbalanceamento. **Três**, comunicação entre processos: cada leitura e escrita no dicionário
> do Manager é uma ida e volta por pipe a outro processo, e criar oito processos também custa.
> **Quatro**, a espera na trava: milissegundos — desprezível, porque travamos só a soma, não a
> simulação."

> "Conclusão: mesma resposta que a sequencial, verificada por hash, [Z] vezes mais rápido em 8
> núcleos, e para a política pública: 40 % de cobertura priorizando idosos já evita o colapso
> hospitalar neste modelo. Obrigado(a)."

---

## Arguição — quem responde o quê

O professor pergunta a cada um sobre uma parte que **não** apresentou. Cada integrante estuda
com atenção as duas partes vizinhas; as respostas curtas estão em [roteiro.md](roteiro.md).

| Integrante | Apresentou | Deve dominar para a arguição |
|---|---|---|
| 1 | Problema | seção crítica (o que é a corrida, por que só a soma tem trava) e Amdahl |
| 2 | Seção crítica | o modelo (R0, unidade de trabalho, por que é determinístico) e a execução |
| 3 | Execução | a seção crítica (Lock vs. semáforo, Manager não basta) e o ganho (f, teto) |
| 4 | Ganho | o problema (por que Monte Carlo) e a fila dinâmica (por que não divisão estática) |

Três respostas que todos precisam saber dizer em uma frase:

1. **Por que processos?** GIL: só uma thread executa Python por vez; o trabalho é 100 % CPU.
2. **Onde está a seção crítica?** `agregar()` — ler, somar, escrever no `Manager().dict()` — protegida por `multiprocessing.Lock` só em volta da soma.
3. **Por que 8 processos não dão 8×?** Clock cai com todos os núcleos ativos, fila desbalanceada no fim, custo de IPC e de criar processos; a trava não é o gargalo (ms).
