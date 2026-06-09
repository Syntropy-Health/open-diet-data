#!/usr/bin/env bash
# Build paper.pdf from paper.tex (natbib + bibtex). Run from arxiv-package/.
set -e
pdflatex -interaction=nonstopmode -halt-on-error paper.tex >/dev/null
bibtex paper >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error paper.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error paper.tex >/dev/null
echo "built paper.pdf ($(wc -c < paper.pdf) bytes)"
