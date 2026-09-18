# Provisionamento na nuvem (AWS)

| Item | Valor |
|---|---|
| Provedor / região | AWS, `sa-east-1` (São Paulo) |
| Zona | `sa-east-1a` |
| Tipo de instância | `c6i.2xlarge` — 8 vCPUs (4 núcleos físicos com hyper-threading), 16 GiB, otimizada para CPU |
| Imagem | Ubuntu Server 24.04 LTS (Canonical) |
| Grupo de segurança | `sd-vacinacao-sg` |

## Regras do grupo de segurança

| Direção | Porta | Protocolo | Origem | Função |
|---|---|---|---|---|
| Entrada | 22 | TCP | **IP(s) da equipe /32** | administrativa (SSH) — restrita |
| Entrada | 8080 | TCP | `0.0.0.0/0` | serviço HTTP da aplicação — pública |
| Saída | todas | todos | `0.0.0.0/0` | `apt`, `git clone` |

O Terraform recusa `0.0.0.0/0` na porta 22 (bloco `validation` em `variables.tf`) e
o script da CLI também aborta nesse caso.

## Opção A — Terraform

```bash
cd nuvem/terraform
terraform init
terraform apply \
  -var='ip_equipe=["203.0.113.10/32","198.51.100.7/32"]' \
  -var='chave_ssh=NOME-DA-CHAVE' \
  -var='repositorio=https://github.com/EQUIPE/REPO.git'
terraform output          # ip_publico, servico, ssh
terraform destroy         # ao terminar, para não gerar custo
```

Descubra o IP da equipe com `curl https://checkip.amazonaws.com` (cada integrante que
for acessar por SSH precisa constar na lista).

## Opção B — AWS CLI

```bash
chmod +x nuvem/criar_instancia_aws.sh
nuvem/criar_instancia_aws.sh NOME-DA-CHAVE https://github.com/EQUIPE/REPO.git 203.0.113.10/32
```

## Depois de subir

```bash
ssh -i chave.pem ubuntu@IP
cd projeto
nproc                                              # confirma 8 vCPUs
python3 src/benchmark.py --perfil completo --repeticoes 3 --processos 1 2 4 8
cat resultados/benchmark_completo.md               # tabela para o relatório
```

Serviço: `http://IP:8080/` (tabela de resultados), `http://IP:8080/saude`.

## O que mostrar ao vivo no console

1. **EC2 → Instâncias**: a instância `sd-vacinacao`, estado *running*, tipo `c6i.2xlarge`,
   zona `sa-east-1a`.
2. **Grupo de segurança → Regras de entrada**: 22/TCP com origem no IP da equipe;
   8080/TCP com origem `0.0.0.0/0`.
3. Terminal SSH aberto na instância rodando `sequencial.py` e `paralelo.py`.
4. Navegador em `http://IP:8080/` para provar que só a porta do serviço está aberta
   (e `nc -zv IP 22` de fora da rede da equipe falhando, se houver tempo).

## Custo

`c6i.2xlarge` em São Paulo custa cerca de US$ 0,55/hora sob demanda. Crie a instância
pouco antes de medir/apresentar e **destrua ao terminar**. Se o crédito for limitado,
`c6i.xlarge` (4 vCPUs) funciona com os mesmos scripts — ajuste `tipo_instancia`.
