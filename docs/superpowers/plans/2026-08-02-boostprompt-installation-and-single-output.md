# BoostPrompt Installation and Single Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BoostPrompt produce one actionable Markdown document and install its selected Claude Code/Codex skill plus optional DuckDuckGo MCP through a safe, testable CLI.

**Architecture:** Keep the two host-specific skill trees and preserve their existing model-specific references. Update only the shared final-document contract in `SKILL.md`. Implement installation in `install.py` with only Python’s standard library; `install.sh` is a minimal Bash delegator. Tests invoke the installer in temporary homes with stubbed host CLIs, so no test touches a real configuration.

**Tech Stack:** Python 3 standard library (`argparse`, `pathlib`, `shutil`, `subprocess`, `unittest`), Bash, Markdown, MIT license text.

## Global Constraints

- Preserve the existing minimum of 30 and maximum of 50 answered questions.
- Produce exactly one final Markdown with an execution-task list and no additional generated artifacts.
- Preserve both `references/best-pratices-mk.md` files unchanged, including their harness-specific model routing.
- Do not add package dependencies or install Python, `uv`, Codex, Claude Code, or MCP servers automatically.
- Copy only `boostprompt` beneath the harness explicitly selected by `--harness`.
- Configure `ddg-search` through the harness CLI only when it does not already exist.
- Run external commands as argument lists (`shell=False`); never compose shell command strings.
- `--dry-run` must perform no copy, directory creation, dependency check, or external command.
- Tests must replace `HOME` and `PATH`; they must never read or write a real user configuration.
- Do not commit any file without separate user approval.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `install.py` | Argument parsing, selected-skill copy, dependency validation, idempotent MCP configuration, user-facing result codes. |
| `install.sh` | POSIX-friendly launcher for `install.py`. |
| `tests/test_install.py` | Behavioral tests for Python installer and shell launcher using temporary executable stubs. |
| `tests/test_skill_contract.py` | Static contract test for the final Markdown sections required by each host skill. |
| `.claude/skills/boostprompt/SKILL.md` | Claude Code BoostPrompt workflow. |
| `.claude/skills/boostprompt/references/best-pratices-mk.md` | Claude-specific model and stage guidance; preserved unchanged. |
| `.codex/skills/boostprompt/SKILL.md` | Codex BoostPrompt workflow. |
| `.codex/skills/boostprompt/references/best-pratices-mk.md` | Codex-specific model and stage guidance; preserved unchanged. |
| `README.md` | Product overview and documented installation/use flows. |
| `LICENSE` | MIT licensing terms for Airton Lira Junior. |

### Task 1: Specify installer behavior with failing tests

**Files:**
- Create: `tests/test_install.py`

**Interfaces:**
- Consumes: command-line interface `python3 install.py --harness {claude,codex,both} [--skip-mcp] [--dry-run]`.
- Produces: executable specification for file destinations and MCP command argument lists.

- [ ] **Step 1: Write the failing Python-installer and shell-wrapper tests**

Create `tests/test_install.py` with temporary `HOME`, a temporary executable directory, and a command log. The CLI stubs must return success for all commands except `mcp get ddg-search`, which returns success only when `MCP_EXISTS=1`.

```python
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.py"
SHELL_INSTALLER = ROOT / "install.sh"


class InstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.sandbox = Path(self.temp_dir.name)
        self.home = self.sandbox / "home"
        self.bin_dir = self.sandbox / "bin"
        self.command_log = self.sandbox / "commands.log"
        self.home.mkdir()
        self.bin_dir.mkdir()
        self.command_log.touch()
        for command in ("claude", "codex", "uvx"):
            self._write_command_stub(command)

    def _write_command_stub(self, name: str) -> None:
        executable = self.bin_dir / name
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "with Path(os.environ['COMMAND_LOG']).open('a', encoding='utf-8') as log:\n"
            "    log.write(Path(sys.argv[0]).name + ' ' + ' '.join(args) + '\\n')\n"
            "if args == ['mcp', 'get', 'ddg-search']:\n"
            "    raise SystemExit(0 if os.environ.get('MCP_EXISTS') == '1' else 1)\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    def run_installer(self, *args: str, **extra_env: str) -> subprocess.CompletedProcess[str]:
        environment = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "COMMAND_LOG": str(self.command_log),
            **extra_env,
        }
        return subprocess.run(
            [sys.executable, str(INSTALLER), *args],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def commands(self) -> list[str]:
        return self.command_log.read_text(encoding="utf-8").splitlines()


class PythonInstallerTests(InstallerTestCase):
    def test_installs_claude_skill_and_adds_mcp(self) -> None:
        result = self.run_installer("--harness", "claude")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".claude/skills/boostprompt/SKILL.md").is_file())
        self.assertFalse((self.home / ".agents/skills/boostprompt").exists())
        self.assertEqual(
            self.commands(),
            [
                "claude mcp get ddg-search",
                "claude mcp add --scope user ddg-search -- uvx duckduckgo-mcp-server",
            ],
        )

    def test_installs_codex_skill_in_user_skill_directory(self) -> None:
        result = self.run_installer("--harness", "codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".agents/skills/boostprompt/SKILL.md").is_file())
        self.assertFalse((self.home / ".claude/skills/boostprompt").exists())
        self.assertEqual(
            self.commands(),
            [
                "codex mcp get ddg-search",
                "codex mcp add ddg-search -- uvx duckduckgo-mcp-server",
            ],
        )

    def test_installs_both_harnesses(self) -> None:
        result = self.run_installer("--harness", "both")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".claude/skills/boostprompt/SKILL.md").is_file())
        self.assertTrue((self.home / ".agents/skills/boostprompt/SKILL.md").is_file())
        self.assertIn("claude mcp add --scope user ddg-search -- uvx duckduckgo-mcp-server", self.commands())
        self.assertIn("codex mcp add ddg-search -- uvx duckduckgo-mcp-server", self.commands())

    def test_skip_mcp_copies_skill_without_external_calls(self) -> None:
        result = self.run_installer("--harness", "claude", "--skip-mcp")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".claude/skills/boostprompt/SKILL.md").is_file())
        self.assertEqual(self.commands(), [])

    def test_dry_run_writes_nothing_and_runs_no_commands(self) -> None:
        result = self.run_installer("--harness", "both", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".agents").exists())
        self.assertEqual(self.commands(), [])

    def test_existing_mcp_is_preserved(self) -> None:
        result = self.run_installer("--harness", "claude", MCP_EXISTS="1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.commands(), ["claude mcp get ddg-search"])

    def test_invalid_harness_fails(self) -> None:
        result = self.run_installer("--harness", "unsupported")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_missing_uvx_fails_before_mcp_add(self) -> None:
        (self.bin_dir / "uvx").unlink()
        result = self.run_installer("--harness", "claude")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uvx", result.stderr)
        self.assertEqual(self.commands(), [])


class ShellWrapperTests(InstallerTestCase):
    def test_shell_wrapper_delegates_to_python_installer(self) -> None:
        environment = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "COMMAND_LOG": str(self.command_log),
        }
        result = subprocess.run(
            ["bash", str(SHELL_INSTALLER), "--harness", "codex", "--skip-mcp"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".agents/skills/boostprompt/SKILL.md").is_file())
        self.assertEqual(self.commands(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the Python-installer tests to verify they fail**

Run: `rtk test python3 tests/test_install.py PythonInstallerTests`

Expected: failures because `install.py` does not yet exist; each requested invocation returns a non-zero Python “cannot open file” result.

- [ ] **Step 3: Run the shell-wrapper test to verify it fails**

Run: `rtk test python3 tests/test_install.py ShellWrapperTests`

Expected: failure because the current shell installer looks for nonexistent `commands/` source files.

### Task 2: Implement the Python multiharness installer

**Files:**
- Create: `install.py`
- Test: `tests/test_install.py`

**Interfaces:**
- Consumes: `--harness`, `--skip-mcp`, and `--dry-run` command-line options.
- Produces: copied skill directory at `~/.claude/skills/boostprompt` and/or `~/.agents/skills/boostprompt`; exit code `0` on success and `1` for missing dependencies or failed host commands.

- [ ] **Step 1: Write the minimum implementation for the tested interface**

Create `install.py` around these concrete interfaces. Keep `subprocess.run` calls list-based and only call `copytree` after `--dry-run` has returned.

```python
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parent
SERVER_NAME = "ddg-search"
SERVER_COMMAND = ["uvx", "duckduckgo-mcp-server"]


class InstallationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Harness:
    name: str
    source: Path
    destination: Path
    cli: str
    mcp_add_command: tuple[str, ...]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instala a skill BoostPrompt para Claude Code e Codex.")
    parser.add_argument("--harness", required=True, choices=("claude", "codex", "both"))
    parser.add_argument("--skip-mcp", action="store_true", help="Instala somente a skill.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra as ações sem modificar arquivos.")
    return parser.parse_args(argv)


def selected_harnesses(value: str) -> tuple[str, ...]:
    return ("claude", "codex") if value == "both" else (value,)


def harnesses() -> dict[str, Harness]:
    home = Path.home()
    return {
        "claude": Harness(
            "claude", ROOT / ".claude/skills/boostprompt", home / ".claude/skills/boostprompt", "claude",
            ("claude", "mcp", "add", "--scope", "user", SERVER_NAME, "--", *SERVER_COMMAND),
        ),
        "codex": Harness(
            "codex", ROOT / ".codex/skills/boostprompt", home / ".agents/skills/boostprompt", "codex",
            ("codex", "mcp", "add", SERVER_NAME, "--", *SERVER_COMMAND),
        ),
    }


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise InstallationError(f"Dependência não encontrada no PATH: {command}")


def copy_skill(harness: Harness, dry_run: bool) -> None:
    if not harness.source.is_dir():
        raise InstallationError(f"Skill de origem não encontrada: {harness.source}")
    if dry_run:
        print(f"[dry-run] Copiaria {harness.source} para {harness.destination}")
        return
    shutil.copytree(harness.source, harness.destination, dirs_exist_ok=True)
    print(f"Skill instalada para {harness.name}: {harness.destination}")


def configure_mcp(harness: Harness, dry_run: bool) -> None:
    get_command = [harness.cli, "mcp", "get", SERVER_NAME]
    if dry_run:
        print(f"[dry-run] Verificaria {' '.join(get_command)}")
        print(f"[dry-run] Executaria {' '.join(harness.mcp_add_command)} se o servidor não existir")
        return
    require_command(harness.cli)
    require_command("uvx")
    existing = subprocess.run(get_command, text=True, capture_output=True, check=False)
    if existing.returncode == 0:
        print(f"MCP '{SERVER_NAME}' já existe para {harness.name}; configuração preservada.")
        return
    added = subprocess.run(list(harness.mcp_add_command), text=True, capture_output=True, check=False)
    if added.returncode != 0:
        raise InstallationError(added.stderr.strip() or f"Não foi possível configurar o MCP para {harness.name}.")
    print(f"MCP '{SERVER_NAME}' configurado para {harness.name}.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        for name in selected_harnesses(args.harness):
            harness = harnesses()[name]
            copy_skill(harness, args.dry_run)
            if not args.skip_mcp:
                configure_mcp(harness, args.dry_run)
    except InstallationError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run Python-installer tests to verify they pass**

Run: `rtk test python3 tests/test_install.py PythonInstallerTests`

Expected: `Ran 8 tests` and `OK`; both copy destinations and all MCP command lists match exactly.

- [ ] **Step 3: Refactor only if the tests remain green**

Keep `Harness` immutable and keep destination calculation inside `harnesses()` so `Path.home()` respects each test’s temporary `HOME`. Do not add configuration-file writing, package installation, or shell execution.

### Task 3: Replace the shell installer with a thin Python launcher

**Files:**
- Modify: `install.sh`
- Test: `tests/test_install.py`

**Interfaces:**
- Consumes: every argument supplied to `install.sh`.
- Produces: the same exit code and output as `python3 install.py`.

- [ ] **Step 1: Run the shell-wrapper test to verify the existing script still fails**

Run: `rtk test python3 tests/test_install.py ShellWrapperTests`

Expected: failure from the old `commands/` source paths.

- [ ] **Step 2: Replace `install.sh` with the delegation-only implementation**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$ROOT_DIR/install.py" "$@"
```

- [ ] **Step 3: Run the wrapper and syntax checks to verify they pass**

Run: `rtk proxy bash -n install.sh && rtk test python3 tests/test_install.py ShellWrapperTests`

Expected: zero exit status; the Codex skill exists below the test home’s `.agents/skills/boostprompt` directory and the command log remains empty due to `--skip-mcp`.

### Task 4: Update the skill contract and remove SDD-style reference phases

**Files:**
- Create: `tests/test_skill_contract.py`
- Modify: `.claude/skills/boostprompt/SKILL.md`
- Modify: `.claude/skills/boostprompt/references/best-pratices-mk.md`
- Modify: `.codex/skills/boostprompt/SKILL.md`
- Modify: `.codex/skills/boostprompt/references/best-pratices-mk.md`

**Interfaces:**
- Consumes: the accumulated answers and optional search sources from the current interview flow.
- Produces: one Markdown with decisions, execution tasks, acceptance criteria, validation, pending execution items, and sources when research was used.

- [ ] **Step 1: Write the failing static skill-contract test**

Create `tests/test_skill_contract.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    ROOT / ".claude/skills/boostprompt/SKILL.md",
    ROOT / ".codex/skills/boostprompt/SKILL.md",
)
REFERENCES = (
    ROOT / ".claude/skills/boostprompt/references/best-pratices-mk.md",
    ROOT / ".codex/skills/boostprompt/references/best-pratices-mk.md",
)


class SkillContractTests(unittest.TestCase):
    def test_skill_variants_are_identical_and_keep_interview_bounds(self) -> None:
        contents = [path.read_text(encoding="utf-8") for path in SKILLS]

        self.assertEqual(contents[0], contents[1])
        self.assertIn("no mínimo 30 perguntas respondidas", contents[0])
        self.assertIn("no máximo 50 perguntas", contents[0])

    def test_final_output_requires_actionable_sections(self) -> None:
        content = SKILLS[0].read_text(encoding="utf-8")

        for section in (
            "## 16. Decisões consolidadas",
            "## 17. Plano de execução",
            "## 18. Critérios de aceite",
            "## 19. Estratégia de validação",
            "## 20. Pendências para execução",
            "## 21. Referências consultadas",
        ):
            self.assertIn(section, content)

    def test_reference_variants_are_identical_and_do_not_define_sdd_phases(self) -> None:
        contents = [path.read_text(encoding="utf-8") for path in REFERENCES]

        self.assertEqual(contents[0], contents[1])
        self.assertNotIn("Fase 1 — Planejamento com Opus", contents[0])
        self.assertNotIn("Fase 2 — Execução com Sonnet", contents[0])
        self.assertIn("Plano de execução", contents[0])
        self.assertIn("Estratégia de validação", contents[0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `rtk test python3 tests/test_skill_contract.py`

Expected: failure because the existing final document has no sections 16–21 and the current reference contains Opus/Sonnet execution phases.

- [ ] **Step 3: Update both `SKILL.md` files with the same final-document contract**

Keep all interview rules intact. Replace the final-document outline with sections 1–15 already present, then append the following headings and imperative requirements:

```markdown
## 16. Decisões consolidadas
Registre cada decisão relevante, sua justificativa, as alternativas descartadas e o trade-off aceito.

## 17. Plano de execução
Crie tarefas priorizadas e verificáveis. Para cada tarefa, informe: objetivo, entregável, dependências, áreas ou arquivos afetados quando conhecidos, critério de pronto e como validar. Em demandas de pesquisa, substitua tarefas de código por hipóteses, fontes, método e evidência esperada.

## 18. Critérios de aceite
Liste condições observáveis de negócio, produto, técnica, segurança e operação necessárias para considerar o objetivo concluído.

## 19. Estratégia de validação
Defina testes automatizados, validações manuais, métricas, observabilidade, revisão de segurança ou avaliação de fontes adequadas à solução. Não invente comandos, arquivos ou ferramentas não confirmados no contexto.

## 20. Pendências para execução
Liste somente decisões, acessos, dados ou aprovações que realmente bloqueiem a execução. Diferencie pendências de riscos já aceitos.

## 21. Referências consultadas
Quando houver busca externa, liste URL, título ou origem, data de consulta e qual decisão a referência fundamentou. Quando não houver busca, declare que a recomendação foi feita em modo degradado.

## 22. Prompt mestre para implementação
Forneça um prompt em pt-BR que use exclusivamente as decisões e restrições do mesmo Markdown, sem solicitar um novo discovery ou criar artefatos de SDD.
```

- [ ] **Step 4: Replace both `best-pratices-mk.md` files with the same output-only guidance**

Use this structure in both files:

```markdown
# Objetivo

Use esta referência apenas para complementar o Markdown final do BoostPrompt. Não crie fases de SDD, não troque de modelo e não execute tarefas durante a entrevista.

## Princípios da saída

- Entregue um único documento Markdown autocontido em pt-BR.
- Diferencie fatos fornecidos, premissas, decisões e pendências.
- Transforme decisões em tarefas pequenas, priorizadas e verificáveis.
- Adapte a validação ao tipo de demanda: implementação, desenvolvimento, operação ou pesquisa.
- Registre referências somente quando houver busca externa disponível.

## Qualidade do plano de execução

Cada tarefa deve declarar objetivo, entregável, dependências, critério de pronto e método de validação. Evite tarefas genéricas como “implementar tudo” ou “testar o sistema”.

## Qualidade da validação

Use condições observáveis. Para código, prefira testes e verificações de comportamento; para pesquisa, explicite hipótese, fonte, método de comparação e evidência; para operação, defina métricas, alertas e responsáveis quando conhecidos.
```

- [ ] **Step 5: Run the contract test to verify it passes**

Run: `rtk test python3 tests/test_skill_contract.py`

Expected: `Ran 3 tests` and `OK`; both pairs of host files are byte-for-byte equal, preserve 30–50 questions, require the new output sections, and no longer prescribe SDD phases.

### Task 5: Rewrite public documentation and add the MIT license

**Files:**
- Modify: `README.md`
- Create: `LICENSE`

**Interfaces:**
- Consumes: a locally cloned project and installed Claude Code and/or Codex CLI.
- Produces: unambiguous, copy-pasteable installation, usage, validation, and removal guidance.

- [ ] **Step 1: Replace the README with the agreed information architecture**

Write the README in pt-BR with these exact top-level sections, in this order:

```markdown
# BoostPrompt

## O que é
## O que você recebe ao final
## Compatibilidade
## Instalação rápida
## Opções do instalador
## MCP DuckDuckGo
## Como usar
## Estrutura do repositório
## Verificação e desinstalação
## Limitações e escopo
## Roadmap
## Autor
## Licença
```

The quick-start block must contain all of these commands:

```bash
python3 install.py --harness claude
python3 install.py --harness codex
python3 install.py --harness both
./install.sh --harness codex --skip-mcp
./install.sh --harness both --dry-run
```

Document the MCP commands exactly as installed, the prerequisite `uvx`, the Claude invocation `/boostprompt`, and the Codex invocation `$boostprompt`. State that the current skill still conducts 30–50 questions and that it produces one final Markdown with decisions, tasks, acceptance criteria, validation, pending items, and research references. Credit:

```markdown
Criado por [Airton Lira Junior](https://www.linkedin.com/in/airton-de-souza-lira-junior-6b81a661/).
```

- [ ] **Step 2: Add the MIT license text**

Create `LICENSE` with the standard MIT grant, the copyright header `Copyright (c) 2026 Airton Lira Junior`, and the standard warranty disclaimer.

- [ ] **Step 3: Validate documentation references mechanically**

Run: `rtk grep "install.py --harness|/boostprompt|\\$boostprompt|Airton Lira Junior|linkedin.com|ddg-search" README.md && rtk read LICENSE`

Expected: every documented command, invocation, author reference, and MCP name appears; the license identifies Airton Lira Junior and contains the MIT permission and warranty clauses.

### Task 6: Execute the complete verification suite and prepare handoff

**Files:**
- Verify: `install.py`
- Verify: `install.sh`
- Verify: `tests/test_install.py`
- Verify: `tests/test_skill_contract.py`
- Verify: `README.md`
- Verify: `LICENSE`

**Interfaces:**
- Consumes: complete working tree after Tasks 1–5.
- Produces: evidence that all scoped behavior works without modifying a real host setup.

- [ ] **Step 1: Run the automated tests**

Run: `rtk test python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all installer, wrapper, and skill-contract tests pass.

- [ ] **Step 2: Run static syntax checks**

Run: `rtk proxy python3 -m py_compile install.py && rtk proxy bash -n install.sh`

Expected: zero exit status and no output.

- [ ] **Step 3: Run a human-readable simulated install**

Run: `rtk proxy python3 install.py --harness both --dry-run`

Expected: output names only the two source/destination skill copies and the two guarded MCP operations; no user directory or MCP configuration changes occur.

- [ ] **Step 4: Inspect the scoped diff and report results**

Run: `rtk git diff -- README.md install.py install.sh LICENSE tests .claude/skills .codex/skills docs/superpowers`

Expected: only the approved documentation, installer, test, license, and design/plan changes appear. Preserve unrelated untracked files and do not create a commit without explicit user approval.
