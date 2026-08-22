#!/usr/bin/env python3
"""Instala a skill BoostPrompt e, opcionalmente, o MCP remoto Exa."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_NAME = "exa"
SERVER_URL = "https://mcp.exa.ai/mcp"


class InstallationError(RuntimeError):
    """Indica que a instalação não pode prosseguir com segurança."""


@dataclass(frozen=True)
class Harness:
    name: str
    source: Path
    destination: Path
    cli: str
    mcp_add_command: tuple[str, ...]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Instala a skill BoostPrompt para Claude Code e Codex."
    )
    parser.add_argument("--harness", required=True, choices=("claude", "codex", "both"))
    parser.add_argument("--skip-mcp", action="store_true", help="Instala somente a skill.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostra as ações sem modificar arquivos."
    )
    return parser.parse_args(argv)


def selected_harnesses(value: str) -> tuple[str, ...]:
    return ("claude", "codex") if value == "both" else (value,)


def harnesses() -> dict[str, Harness]:
    home = Path.home()
    return {
        "claude": Harness(
            name="claude",
            source=ROOT / ".claude/skills/boostprompt",
            destination=home / ".claude/skills/boostprompt",
            cli="claude",
            mcp_add_command=(
                "claude",
                "mcp",
                "add",
                "--scope",
                "user",
                "--transport",
                "http",
                SERVER_NAME,
                SERVER_URL,
            ),
        ),
        "codex": Harness(
            name="codex",
            source=ROOT / ".codex/skills/boostprompt",
            destination=home / ".agents/skills/boostprompt",
            cli="codex",
            mcp_add_command=(
                "codex",
                "mcp",
                "add",
                SERVER_NAME,
                "--url",
                SERVER_URL,
            ),
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
        print(
            f"[dry-run] Executaria {' '.join(harness.mcp_add_command)} "
            "se o servidor não existir"
        )
        return

    require_command(harness.cli)
    existing = subprocess.run(get_command, text=True, capture_output=True, check=False)
    if existing.returncode == 0:
        print(f"MCP '{SERVER_NAME}' já existe para {harness.name}; configuração preservada.")
        return

    added = subprocess.run(
        list(harness.mcp_add_command), text=True, capture_output=True, check=False
    )
    if added.returncode != 0:
        message = added.stderr.strip() or (
            f"Não foi possível configurar o MCP para {harness.name}."
        )
        raise InstallationError(message)
    print(f"MCP '{SERVER_NAME}' configurado para {harness.name}.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        available_harnesses = harnesses()
        for name in selected_harnesses(args.harness):
            harness = available_harnesses[name]
            copy_skill(harness, args.dry_run)
            if not args.skip_mcp:
                configure_mcp(harness, args.dry_run)
    except InstallationError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
