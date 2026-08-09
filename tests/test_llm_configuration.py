from pathlib import Path

import pytest
from pydantic_ai.models.openai import OpenAIChatModel

from boostprompt.llm import ModelProvider, OpenAICompatibleSettings
from boostprompt.services.discovery_workflow import DiscoveryWorkflowService


def test_default_service_uses_litellm_environment_for_openai_compatible_model(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = tmp_path / "litellm.env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=litellm",
                "LLM_MODEL=litellm/gpt-4.1-mini",
                "LITELLM_BASE_URL=https://litellm.example.test/v1",
                "API_KEY=token-for-test",
                f"DUCKDB_PATH={tmp_path / 'configured.db'}",
            ]
        ),
        encoding="utf-8",
    )
    for name in (
        "API_KEY",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LITELLM_BASE_URL",
        "LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BOOSTPROMPT_ENV_FILE", str(env_file))

    service = DiscoveryWorkflowService.create_default(provider=ModelProvider.LITELLM)
    try:
        model = service.workflow.agents.discovery.agent.model

        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "litellm/gpt-4.1-mini"
        assert model.provider.base_url == "https://litellm.example.test/v1/"
        assert service.repository.db_path == tmp_path / "configured.db"
    finally:
        service.close()


def test_openai_provider_uses_its_own_environment_variables(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "openai.env"
    env_file.write_text(
        "OPENAI_MODEL=gpt-4.1-mini\nOPENAI_API_KEY=token-openai",
        encoding="utf-8",
    )
    for name in (
        "API_KEY",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LITELLM_BASE_URL",
        "LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BOOSTPROMPT_ENV_FILE", str(env_file))

    model = OpenAICompatibleSettings.from_environment(ModelProvider.OPENAI).build_model()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "gpt-4.1-mini"


def test_litellm_provider_requires_a_base_url(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "missing-url.env"
    env_file.write_text("LLM_MODEL=litellm/gpt-4.1-mini\nAPI_KEY=token", encoding="utf-8")
    for name in ("LLM_BASE_URL", "LITELLM_BASE_URL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BOOSTPROMPT_ENV_FILE", str(env_file))

    with pytest.raises(ValueError, match="LITELLM_BASE_URL"):
        OpenAICompatibleSettings.from_environment(ModelProvider.LITELLM)
