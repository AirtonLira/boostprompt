from boostprompt.services.prompt_artifact import PromptArtifactValidator


def complete_prompt() -> str:
    sections = []
    for heading in PromptArtifactValidator.CANONICAL_SECTIONS:
        content = f"Conteúdo específico para {heading}."
        if heading.startswith("## 21."):
            content = "- [source-1] RFC OAuth\n  URL: https://example.com/rfc\n  Fundamenta: autenticação"
        if heading.startswith("## 22."):
            content = (
                "Implemente o objetivo e o escopo respeitando as restrições. Cubra requisitos "
                "funcionais e requisitos não funcionais, arquitetura, dados e integrações, "
                "segurança, testes, observabilidade, entrega e critérios de aceite."
            )
        sections.append(f"{heading}\n\n{content}")
    return "# Prompt Mestre de Implementação - Portal\n\n" + "\n\n".join(sections)


def test_validator_reports_absent_sections_and_master_prompt_topics() -> None:
    report = PromptArtifactValidator().validate(
        "# Prompt Mestre de Implementação - Portal\n\n## 1. Contexto e objetivo\nTexto"
    )

    assert "## 17. Plano de execução" in report.missing_sections
    assert "segurança" in report.missing_prompt_topics
    assert report.valid is False


def test_validator_accepts_one_complete_self_contained_implementation_prompt() -> None:
    report = PromptArtifactValidator().validate(complete_prompt())

    assert report.valid is True
    assert report.missing_sections == []
    assert report.invalid_reference_urls == []


def test_validator_rejects_legacy_scope_and_invalid_reference_url() -> None:
    markdown = complete_prompt().replace(
        "# Prompt Mestre de Implementação - Portal", "# Escopo da Solução"
    )
    markdown = markdown.replace("https://example.com/rfc", "not-a-url")

    report = PromptArtifactValidator().validate(markdown)

    assert report.valid is False
    assert "not-a-url" in report.invalid_reference_urls
    assert report.warnings
