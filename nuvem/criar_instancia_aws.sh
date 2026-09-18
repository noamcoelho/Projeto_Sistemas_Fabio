#!/bin/bash
# Alternativa ao Terraform: cria o mesmo grupo de segurança e a mesma instância
# usando apenas a AWS CLI. Requer `aws configure` feito antes.
#
# Uso:
#   ./criar_instancia_aws.sh <nome-da-chave-ssh> <url-do-repositorio> [cidr-da-equipe]
#   ex.: ./criar_instancia_aws.sh minha-chave https://github.com/equipe/projeto.git 203.0.113.10/32
#
# Se o CIDR não for informado, usa o IP público atual da máquina que executa o script.
set -euo pipefail

CHAVE=${1:?informe o nome do par de chaves}
REPOSITORIO=${2:?informe a URL do repositório}
CIDR_EQUIPE=${3:-"$(curl -s https://checkip.amazonaws.com)/32"}

REGIAO=sa-east-1          # São Paulo
ZONA=sa-east-1a
TIPO=c6i.2xlarge          # 8 vCPUs (4 núcleos físicos), otimizada para CPU
NOME=sd-vacinacao

if [[ "$CIDR_EQUIPE" == "0.0.0.0/0" ]]; then
  echo "ERRO: a porta administrativa (22) não pode ficar aberta para qualquer origem." >&2
  exit 1
fi

echo "== AMI Ubuntu 24.04 mais recente"
AMI=$(aws ec2 describe-images --region "$REGIAO" --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
echo "   $AMI"

echo "== Grupo de segurança"
VPC=$(aws ec2 describe-vpcs --region "$REGIAO" --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 create-security-group --region "$REGIAO" --vpc-id "$VPC" \
  --group-name "$NOME-sg" --description "SSH restrito a equipe, HTTP 8080 publico" \
  --query GroupId --output text)
# porta administrativa: só a equipe
aws ec2 authorize-security-group-ingress --region "$REGIAO" --group-id "$SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$CIDR_EQUIPE,Description='SSH somente da equipe'}]"
# porta do serviço: aberta
aws ec2 authorize-security-group-ingress --region "$REGIAO" --group-id "$SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=8080,ToPort=8080,IpRanges=[{CidrIp=0.0.0.0/0,Description='Servico HTTP'}]"
echo "   $SG (22 <- $CIDR_EQUIPE ; 8080 <- 0.0.0.0/0)"

echo "== Instância"
USERDATA=$(sed "s|\${REPOSITORIO}|$REPOSITORIO|g" "$(dirname "$0")/setup_instancia.sh")
ID=$(aws ec2 run-instances --region "$REGIAO" --image-id "$AMI" --instance-type "$TIPO" \
  --placement "AvailabilityZone=$ZONA" --key-name "$CHAVE" --security-group-ids "$SG" \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=16,VolumeType=gp3}' \
  --user-data "$USERDATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NOME},{Key=Projeto,Value=SD-Etapa1}]" \
  --query 'Instances[0].InstanceId' --output text)
echo "   $ID — aguardando ficar em execução..."
aws ec2 wait instance-running --region "$REGIAO" --instance-ids "$ID"
IP=$(aws ec2 describe-instances --region "$REGIAO" --instance-ids "$ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

cat <<EOF

Instância pronta (a instalação do projeto leva ~2 min a mais):
  id:       $ID
  região:   $REGIAO / zona: $ZONA / tipo: $TIPO
  ssh:      ssh -i $CHAVE.pem ubuntu@$IP
  serviço:  http://$IP:8080/

Para encerrar (evitar custo):
  aws ec2 terminate-instances --region $REGIAO --instance-ids $ID
  aws ec2 wait instance-terminated --region $REGIAO --instance-ids $ID
  aws ec2 delete-security-group --region $REGIAO --group-id $SG
EOF
