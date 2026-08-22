"""Serviços de aplicação que conectam TUI, workflow e persistência."""

from typing import Any

__all__ = ["DiscoveryWorkflowService"]


def __getattr__(name: str) -> Any:
    """Evita carregar o workflow enquanto submódulos de serviço são importados."""

    if name == "DiscoveryWorkflowService":
        from .discovery_workflow import DiscoveryWorkflowService

        return DiscoveryWorkflowService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
