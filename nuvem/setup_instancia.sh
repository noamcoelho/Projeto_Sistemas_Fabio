#!/bin/bash
# Script de inicialização da instância (user-data). Roda como root no primeiro boot.
# Instala Python, clona o repositório e sobe o serviço HTTP na porta 8080 como
# serviço do systemd. Log: /var/log/cloud-init-output.log
#
# Usado pelo Terraform (templatefile) e pelo criar_instancia_aws.sh.
# A variável ${REPOSITORIO} é substituída pela URL do repositório git.
set -eux

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 git htop

USUARIO=ubuntu
DESTINO=/home/$USUARIO/projeto
sudo -u $USUARIO git clone "${REPOSITORIO}" "$DESTINO"

# teste de fumaça: gera um resultado e confirma que sequencial == paralelo
cd "$DESTINO"
sudo -u $USUARIO python3 src/sequencial.py --perfil rapido --silencioso
sudo -u $USUARIO python3 src/paralelo.py  --perfil rapido --silencioso
sudo -u $USUARIO python3 src/verificar.py resultados/sequencial_rapido.json resultados/paralelo_rapido.json

cat > /etc/systemd/system/sd-vacinacao.service <<EOF
[Unit]
Description=Simulador de vacinacao - servico HTTP (porta 8080)
After=network.target

[Service]
User=$USUARIO
WorkingDirectory=$DESTINO
ExecStart=/usr/bin/python3 $DESTINO/src/servidor.py --porta 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now sd-vacinacao.service
echo "instalacao concluida"
