variable "regiao" {
  description = "Região AWS"
  type        = string
  default     = "sa-east-1" # São Paulo
}

variable "zona" {
  description = "Zona de disponibilidade"
  type        = string
  default     = "sa-east-1a"
}

variable "tipo_instancia" {
  description = "Tipo da instância (c6i.2xlarge = 8 vCPUs / 4 núcleos físicos, otimizada para CPU)"
  type        = string
  default     = "c6i.2xlarge"
}

variable "chave_ssh" {
  description = "Nome do par de chaves EC2 já criado na região"
  type        = string
}

variable "ip_equipe" {
  description = "Lista de CIDRs da equipe autorizados a acessar a porta 22 (ex.: [\"203.0.113.10/32\"])"
  type        = list(string)

  validation {
    condition     = !contains(var.ip_equipe, "0.0.0.0/0")
    error_message = "A porta administrativa não pode ficar aberta para qualquer origem."
  }
}

variable "repositorio" {
  description = "URL do repositório git do projeto (clonado na inicialização da instância)"
  type        = string
}
