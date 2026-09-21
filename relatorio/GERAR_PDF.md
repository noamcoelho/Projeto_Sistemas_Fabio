# Como gerar o PDF do relatório

O relatório está em `relatorio.md` (Markdown com cabeçalho YAML). Três caminhos:

## 1. Pandoc (melhor resultado)

```bash
# Windows: winget install JohnMacFarlane.Pandoc ; instalar MiKTeX
# Ubuntu:  sudo apt install pandoc texlive-latex-recommended texlive-lang-portuguese
cd relatorio
pandoc relatorio.md -o relatorio.pdf --pdf-engine=xelatex -V mainfont="DejaVu Sans"
```

## 2. VS Code

Instale a extensão **Markdown PDF** (yzane), abra `relatorio.md`, `Ctrl+Shift+P` →
*Markdown PDF: Export (pdf)*.

## 3. Navegador

Extensão **Markdown Preview Enhanced** → botão direito na prévia → *Open in Browser* →
imprimir como PDF (margens 2 cm).

## Antes de gerar

- [ ] Preencher nomes da equipe e URL do repositório no cabeçalho.
- [ ] Colar a tabela de `resultados/benchmark_completo.md` (3 repetições, mesma máquina).
- [ ] Atualizar a tabela do teste de corrida se rodar em outra máquina.
- [ ] Preencher os valores X, Y, Z da conclusão.
- [ ] Conferir que ficou em **até seis páginas**.
