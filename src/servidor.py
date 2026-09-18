"""Serviço HTTP (porta 8080) que publica os resultados da simulação.

É a "porta do serviço" liberada no grupo de segurança da instância. Mostra a
tabela de cenários, o benchmark e permite disparar uma execução pela URL.

Uso:
    python src/servidor.py --porta 8080

Rotas:
    GET /                      página HTML com o resumo
    GET /saude                 {"status": "ok"}
    GET /resultados            lista os JSON disponíveis
    GET /resultados/<nome>     conteúdo de um arquivo de resultado
    GET /executar?modo=paralelo&perfil=rapido&processos=4   roda e devolve os tempos
"""

import argparse
import html
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from comum import PASTA_RESULTADOS, PERFIS, cpus_disponiveis, resumo_tabela

SRC = Path(__file__).resolve().parent


def executar(modo, perfil, processos):
    script = "paralelo.py" if modo == "paralelo" else "sequencial.py"
    cmd = [sys.executable, str(SRC / script), "--perfil", perfil, "--silencioso"]
    if modo == "paralelo":
        cmd += ["-p", str(processos)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
    linha = [l for l in proc.stdout.splitlines() if l.startswith("TEMPOS ")][-1]
    return json.loads(linha[len("TEMPOS "):])


def pagina():
    partes = ["<!doctype html><meta charset='utf-8'><title>Simulador de vacinação</title>",
              "<style>body{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}"
              "pre{background:#f4f4f4;padding:1rem;overflow-x:auto}</style>",
              "<h1>Simulação de políticas de vacinação — SIR paralelo</h1>",
              f"<p>CPUs disponíveis nesta instância: <b>{cpus_disponiveis()}</b></p>",
              "<p>Executar: " + " | ".join(
                  f"<a href='/executar?modo={m}&perfil={p}&processos={cpus_disponiveis()}'>{m} {p}</a>"
                  for p in ("rapido", "demo") for m in ("sequencial", "paralelo")) + "</p>"]
    for arq in sorted(PASTA_RESULTADOS.glob("*.json")) if PASTA_RESULTADOS.exists() else []:
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        partes.append(f"<h2>{html.escape(arq.name)}</h2>")
        if "cenarios" in dados:
            partes.append(f"<pre>{html.escape(resumo_tabela(dados))}</pre>")
        elif "paralelo" in dados:
            md = arq.with_suffix(".md")
            if md.exists():
                partes.append(f"<pre>{html.escape(md.read_text(encoding='utf-8'))}</pre>")
        partes.append(f"<p><a href='/resultados/{html.escape(arq.name)}'>JSON completo</a></p>")
    return "\n".join(partes)


class Manipulador(BaseHTTPRequestHandler):
    def _responder(self, corpo, tipo="application/json", codigo=200):
        dados = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path == "/":
                self._responder(pagina(), "text/html")
            elif url.path == "/saude":
                self._responder(json.dumps({"status": "ok", "cpus": cpus_disponiveis()}))
            elif url.path == "/resultados":
                nomes = sorted(p.name for p in PASTA_RESULTADOS.glob("*.json")) if PASTA_RESULTADOS.exists() else []
                self._responder(json.dumps(nomes))
            elif url.path.startswith("/resultados/"):
                nome = Path(url.path.split("/", 2)[2]).name
                arq = PASTA_RESULTADOS / nome
                if arq.is_file() and arq.suffix == ".json":
                    self._responder(arq.read_bytes())
                else:
                    self._responder('{"erro": "não encontrado"}', codigo=404)
            elif url.path == "/executar":
                modo = q.get("modo", "paralelo")
                perfil = q.get("perfil", "rapido")
                procs = int(q.get("processos", cpus_disponiveis()))
                if modo not in ("sequencial", "paralelo") or perfil not in PERFIS:
                    self._responder('{"erro": "parâmetros inválidos"}', codigo=400)
                    return
                self._responder(json.dumps(executar(modo, perfil, procs), ensure_ascii=False, indent=1))
            else:
                self._responder('{"erro": "rota inexistente"}', codigo=404)
        except Exception as exc:  # noqa: BLE001 - serviço de demonstração
            self._responder(json.dumps({"erro": str(exc)}), codigo=500)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    servidor = ThreadingHTTPServer((args.host, args.porta), Manipulador)
    print(f"servindo em http://{args.host}:{args.porta}/  (Ctrl+C para parar)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
