"""
Entry point para execução como módulo: python -m boostprompt.cli

Uso:
    uv run python -m boostprompt.cli
    ou
    boostprompt (após instalação)
"""
from .tui_main import main

__all__ = ["main"]


if __name__ == "__main__":
    main()