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
        for command in ("claude", "codex"):
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
            "if args == ['mcp', 'get', 'exa']:\n"
            "    raise SystemExit(0 if os.environ.get('MCP_EXISTS') == '1' else 1)\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    def run_installer(
        self, *args: str, **extra_env: str
    ) -> subprocess.CompletedProcess[str]:
        path = extra_env.pop("PATH", f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}")
        environment = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": path,
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
                "claude mcp get exa",
                "claude mcp add --scope user --transport http exa https://mcp.exa.ai/mcp",
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
                "codex mcp get exa",
                "codex mcp add exa --url https://mcp.exa.ai/mcp",
            ],
        )

    def test_installs_both_harnesses(self) -> None:
        result = self.run_installer("--harness", "both")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".claude/skills/boostprompt/SKILL.md").is_file())
        self.assertTrue((self.home / ".agents/skills/boostprompt/SKILL.md").is_file())
        self.assertIn(
            "claude mcp add --scope user --transport http exa https://mcp.exa.ai/mcp",
            self.commands(),
        )
        self.assertIn(
            "codex mcp add exa --url https://mcp.exa.ai/mcp",
            self.commands(),
        )

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
        self.assertEqual(self.commands(), ["claude mcp get exa"])

    def test_invalid_harness_fails(self) -> None:
        result = self.run_installer("--harness", "unsupported")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_missing_harness_fails_before_mcp_add(self) -> None:
        (self.bin_dir / "claude").unlink()
        result = self.run_installer("--harness", "claude", PATH=str(self.bin_dir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("claude", result.stderr)
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
