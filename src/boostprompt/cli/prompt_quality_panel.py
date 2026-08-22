"""Painel persistente que mostra a qualidade do contexto do prompt."""

from textual.widgets import Static

from boostprompt.models.schemas import PromptQualityEvaluation


class PromptQualityPanel(Static):
    """Exibe a avaliação determinística da qualidade do prompt."""

    def __init__(self, evaluation: PromptQualityEvaluation | None = None) -> None:
        super().__init__(id="prompt-quality-panel")
        self.update_evaluation(evaluation)

    def update_evaluation(self, evaluation: PromptQualityEvaluation | None) -> None:
        """Atualiza o painel com o snapshot mais recente da sessão."""

        self.update(self._render_evaluation(evaluation))

    @staticmethod
    def _render_evaluation(evaluation: PromptQualityEvaluation | None) -> str:
        if evaluation is not None and not evaluation.applicable:
            return f"[bold]Avaliação não aplicável[/bold]\n{evaluation.status_text}"

        if evaluation is None:
            evaluation = PromptQualityEvaluation(
                coverage=0,
                decision_clarity=0,
                prompt_readiness=0,
            )

        validation_status = "Validação do documento: aguardando geração."
        if evaluation.validation_report is not None:
            report = evaluation.validation_report
            if report.valid:
                validation_status = "Documento validado."
            else:
                issue = next(
                    iter(
                        [
                            *report.missing_sections,
                            *report.missing_prompt_topics,
                            *report.invalid_reference_urls,
                            *report.warnings,
                        ]
                    ),
                    "lacuna não detalhada",
                )
                validation_status = f"Documento requer revisão: {issue}"

        return "\n".join(
            (
                "[bold]Qualidade do prompt[/bold]",
                f"{evaluation.questions_count}/30 respostas mínimas",
                f"[bold]Cobertura do contexto[/bold]: {evaluation.coverage or 0}/100",
                "Mede os blocos essenciais registrados.",
                f"[bold]Clareza das decisões[/bold]: {evaluation.decision_clarity or 0}/100",
                "Mede o quanto as decisões e restrições estão definidas.",
                f"[bold]Prontidão do prompt[/bold]: {evaluation.prompt_readiness or 0}/100",
                "Indica se há base para gerar um prompt útil.",
                validation_status,
                f"[italic]{evaluation.status_text}[/italic]",
            )
        )
