# Emenda ao Plano — Preservação de Modelo por Harness

Esta emenda substitui somente a Task 4 e a parte de modelos da Task 5 do plano original. Ela foi criada após a orientação explícita do autor para não alterar `references/best-pratices-mk.md`.

## Restrições substituídas

- Não modificar `.claude/skills/boostprompt/references/best-pratices-mk.md`.
- Não modificar `.codex/skills/boostprompt/references/best-pratices-mk.md`.
- Não exigir que as referências Claude e Codex sejam iguais: elas têm roteamento de modelos próprio.
- Preservar Opus para planejamento e Sonnet para execução no Claude.
- Preservar GPT 5.6 Sol para planejamento e GPT 5.6 Terra para execução no Codex.

## Task 4 revisada: Atualizar apenas o contrato do Markdown final

**Arquivos:**

- Modificar: `.claude/skills/boostprompt/SKILL.md`
- Modificar: `.codex/skills/boostprompt/SKILL.md`
- Modificar: `tests/test_skill_contract.py`

**Teste primeiro:** o teste deve percorrer as duas `SKILL.md` e, para cada uma, confirmar a faixa de 30–50 perguntas e a presença das seções 16–21. Ele não deve ler nem comparar as referências.

```python
def test_each_skill_keeps_interview_bounds(self) -> None:
    for path in SKILLS:
        content = path.read_text(encoding="utf-8")
        self.assertIn("no mínimo 30 perguntas respondidas", content)
        self.assertIn("no máximo 50 perguntas", content)

def test_each_skill_requires_actionable_final_sections(self) -> None:
    for path in SKILLS:
        content = path.read_text(encoding="utf-8")
        for section in (
            "## 16. Decisões consolidadas",
            "## 17. Plano de execução",
            "## 18. Critérios de aceite",
            "## 19. Estratégia de validação",
            "## 20. Pendências para execução",
            "## 21. Referências consultadas",
        ):
            self.assertIn(section, content)
```

Após o teste falhar, as duas skills receberão as seções 16–21 e a seção 22 para o prompt mestre, mantendo as seções e regras de entrevista já existentes. Nenhuma alteração deve ser feita nos arquivos dentro de `references/`.

## Task 5 revisada: Documentar o roteamento existente

O README incluirá esta tabela em `## Compatibilidade`, sem modificar as referências instaladas:

| Harness | Planejamento | Execução |
| --- | --- | --- |
| Claude Code | Opus | Sonnet |
| Codex | GPT 5.6 Sol | GPT 5.6 Terra |

O restante da Task 5 — instalação automática, MCP, autor, LinkedIn, licença, validação e desinstalação — permanece inalterado.
