"""Configuração de modelos compatíveis com a API OpenAI para a CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_DATABASE_PATH = "data/boostprompt.db"


class ModelProvider(StrEnum):
    """Provedores disponíveis na seleção inicial da TUI."""

    LITELLM = "litellm"
    OPENAI = "openai"


def _first_configured(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def load_cli_environment() -> None:
    """Carrega o `.env` da CLI sem sobrescrever variáveis já exportadas."""

    env_file = os.getenv("BOOSTPROMPT_ENV_FILE")
    load_dotenv(dotenv_path=env_file or ".env", override=False)


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    """Variáveis necessárias para um endpoint com contrato OpenAI."""

    model_name: str
    base_url: str | None
    api_key: str | None
    database_path: Path

    @classmethod
    def from_environment(cls, provider: ModelProvider) -> OpenAICompatibleSettings:
        load_cli_environment()
        if provider is ModelProvider.LITELLM:
            model_name = _first_configured("LLM_MODEL")
            base_url = _first_configured("LLM_BASE_URL", "LITELLM_BASE_URL")
            api_key = _first_configured("LLM_API_KEY", "LITELLM_API_KEY", "API_KEY")
            if not model_name:
                raise ValueError("Configure LLM_MODEL para usar LiteLLM.")
            if not base_url:
                raise ValueError("Configure LLM_BASE_URL ou LITELLM_BASE_URL para usar LiteLLM.")
            if not api_key:
                raise ValueError("Configure LLM_API_KEY, LITELLM_API_KEY ou API_KEY para usar LiteLLM.")
        else:
            model_name = _first_configured("OPENAI_MODEL", "LLM_MODEL") or DEFAULT_MODEL
            base_url = _first_configured("OPENAI_BASE_URL")
            api_key = _first_configured("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Configure OPENAI_API_KEY para usar OpenAI.")
        return cls(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            database_path=Path(
                _first_configured("DUCKDB_PATH") or DEFAULT_DATABASE_PATH
            ),
        )

    def build_model(self) -> Model:
        provider = OpenAIProvider(base_url=self.base_url, api_key=self.api_key)
        return OpenAIChatModel(self.model_name, provider=provider)
