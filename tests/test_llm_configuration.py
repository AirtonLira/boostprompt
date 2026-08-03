from pathlib import Path

from pydantic_ai.models.openai import OpenAIChatModel

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

    service = DiscoveryWorkflowService.create_default()
    try:
        model = service.workflow.agents.discovery.agent.model

        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "litellm/gpt-4.1-mini"
        assert model.provider.base_url == "https://litellm.example.test/v1/"
        assert service.repository.db_path == tmp_path / "configured.db"
    finally:
        service.close()
