# Provisionamento da instância de computação na AWS (região São Paulo).
#
# Recursos criados:
#   * grupo de segurança "sd-vacinacao-sg":
#       - porta 22 (SSH, administrativa)  -> SOMENTE a partir dos IPs da equipe
#       - porta 8080 (serviço HTTP)       -> qualquer origem
#       - saída liberada
#   * instância EC2 (Ubuntu 24.04) com script de inicialização que instala o
#     projeto e sobe o serviço na porta 8080.
#
# Uso:
#   terraform init
#   terraform apply -var="ip_equipe=[\"203.0.113.10/32\"]" -var="chave_ssh=minha-chave"
#   terraform destroy   # ao final da apresentação, para não gerar custo

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.regiao
}

# AMI Ubuntu 24.04 LTS mais recente publicada pela Canonical
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "padrao" {
  default = true
}

resource "aws_security_group" "sd" {
  name        = "sd-vacinacao-sg"
  description = "Simulador de vacinacao - SSH restrito a equipe, HTTP 8080 publico"
  vpc_id      = data.aws_vpc.padrao.id

  # Porta administrativa: restrita à origem da equipe (NUNCA 0.0.0.0/0)
  ingress {
    description = "SSH somente da equipe"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ip_equipe
  }

  # Porta do serviço: aberta
  ingress {
    description = "Servico HTTP da aplicacao"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Saida liberada (apt, git clone)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "sd-vacinacao-sg", Projeto = "SD-Etapa1" }
}

resource "aws_instance" "sd" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.tipo_instancia
  availability_zone      = var.zona
  key_name               = var.chave_ssh
  vpc_security_group_ids = [aws_security_group.sd.id]

  user_data = templatefile("${path.module}/../setup_instancia.sh", {
    REPOSITORIO = var.repositorio
  })

  root_block_device {
    volume_size = 16
    volume_type = "gp3"
  }

  tags = { Name = "sd-vacinacao", Projeto = "SD-Etapa1" }
}
