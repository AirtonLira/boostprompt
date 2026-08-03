"""Configuração de modelos compatíveis com a API OpenAI para a CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_DATABASE_PATH = "data/boostprompt.db"


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
    def from_environment(cls) -> OpenAICompatibleSettings:
        load_cli_environment()
        return cls(
            model_name=_first_configured("LLM_MODEL") or DEFAULT_MODEL,
            base_url=_first_configured(
                "LLM_BASE_URL", "LITELLM_BASE_URL", "OPENAI_BASE_URL"
            ),
            api_key=_first_configured(
                "LLM_API_KEY", "LITELLM_API_KEY", "API_KEY", "OPENAI_API_KEY"
            ),
            database_path=Path(
                _first_configured("DUCKDB_PATH") or DEFAULT_DATABASE_PATH
            ),
        )

    def build_model(self) -> Model:
        if self.base_url is None and self.api_key is None:
            raise ValueError(
                "Configure LLM_API_KEY (ou OPENAI_API_KEY) para OpenAI, ou "
                "LLM_BASE_URL/LITELLM_BASE_URL para um endpoint compatível."
            )
        provider = OpenAIProvider(base_url=self.base_url, api_key=self.api_key)
        return OpenAIChatModel(self.model_name, provider=provider)
