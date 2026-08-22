"""Falhas de pesquisa que permitem ao discovery continuar em modo degradado."""


class ResearchUnavailableError(RuntimeError):
    """Indica indisponibilidade de um provedor externo sem invalidar a sessão."""
