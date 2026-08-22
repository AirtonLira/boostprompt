from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    ROOT / ".claude/skills/boostprompt/SKILL.md",
    ROOT / ".codex/skills/boostprompt/SKILL.md",
)


class SkillContractTests(unittest.TestCase):
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

    def test_each_skill_requires_exa_evidence_and_one_implementation_prompt(self) -> None:
        for path in SKILLS:
            content = path.read_text(encoding="utf-8")

            for requirement in (
                "web_search_exa",
                "web_fetch_exa",
                "modo degradado",
                "fonte oficial",
                "decisão que a referência fundamentou",
                "# Prompt Mestre de Implementação",
                "## 22. Instruções ao agente implementador",
            ):
                self.assertIn(requirement, content)

    def test_each_skill_supports_a_client_question_guide_mode(self) -> None:
        for path in SKILLS:
            content = path.read_text(encoding="utf-8")

            for requirement in (
                "modo_saida",
                "prompt_desenvolvimento",
                "roteiro_perguntas_cliente",
                "# Perguntas para Discovery com o Cliente",
                "um único documento Markdown",
            ):
                self.assertIn(requirement, content)


if __name__ == "__main__":
    unittest.main()
