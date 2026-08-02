"""
Funções utilitárias para o projeto.
"""
import hashlib
from datetime import datetime


def generate_short_id(text: str, length: int = 8) -> str:
    """Gera um ID curto baseado em hash do texto."""
    hash_obj = hashlib.md5(text.encode())
    return hash_obj.hexdigest()[:length]


def format_timestamp(dt: datetime) -> str:
    """Formata um timestamp para exibiação amigável."""
    return dt.strftime("%d/%m/%Y %H:%M")
