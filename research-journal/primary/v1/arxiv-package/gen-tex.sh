#!/usr/bin/env bash
# Regenerate paper.tex from ../paper.md. Run from arxiv-package/.
set -e
pandoc ../paper.md -o paper.tex --standalone --natbib \
  --include-in-header=preamble.tex \
  --metadata title="Grounded but Not Faithful: Provenance Integrity as a Safety Prerequisite in Multi-Agent LLM Systems for Supplement--Drug Reasoning"
python3 - << 'PY'
t=open('paper.tex').read()
import re
# replace the pandoc references section + empty csl block with a real bibliography + appendix
t=re.sub(r'\\hypertarget\{references\}\{%\n\\section\{References\}\\label\{references\}\}\s*\n+\\hypertarget\{refs\}\{\}\n\\begin\{cslreferences\}\n\\end\{cslreferences\}',
         r'\\bibliography{references}\n\n\\appendix', t, count=1)
open('paper.tex','w').write(t)
print('post-processed: bibliography + appendix' if '\\bibliography{references}' in t else 'WARN: bib hook not inserted')
PY
