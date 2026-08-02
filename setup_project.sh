#!/usr/bin/env bash
#
# Script de setup da estrutura do projeto BoostPrompt CLI
# Preserva arquivos existentes (especialmente skills) e cria a nova estrutura
#
set -e

echo "🚀 Iniciando setup do projeto BoostPrompt CLI..."

# =============================================================================
# 1. Criar estrutura de pastas
# =============================================================================

echo "📁 Criando estrutura de pastas..."

mkdir -p src/boostprompt/agents
mkdir -p src/boostprompt/graph
mkdir -p src/boostprompt/memory
mkdir -p src/boostprompt/models
mkdir -p src/boostprompt/prompts
mkdir -p src/boostprompt/utils
mkdir -p src/boostprompt/cli
mkdir -p tests
mkdir -p data
mkdir -p examples
mkdir -p docs

# =============================================================================
# 2. Criar arquivos __init__.py (para tornar os diretó¬¬¬◊rios pacotes Python)
# =============================================================================

echo "📄 Criando arquivos __init__.py..."

touch src/boostprompt/__init__.py
touch src/boostprompt/agents/__init__.py
touch src/boostprompt/graph/__init__.py
touch src/boostprompt/memory/__init__.py
touch src/boostprompt/models/__init__.py
touch src/boostprompt/prompts/__init__.py
touch src/boostprompt/utils/__init__.py
touch src/boostprompt/cli/__init__.py
touch tests/__init__.py

# =============================================================================
# 3. Criar arquivos base (placeholders) para cada módulo
# =============================================================================

echo "📝 Criando arquivos base dos módulos..."

# --- Agents ---
cat > src/boostprompt/agents/base.py << 'EOF'
"""
Classe base para todos os agentes do BoostPrompt.
Cada agente especializado herdará©© desta classe.
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Classe base para agentes."""

    name: str
    description: str

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executar o agente com o estado atual."""
        pass
EOF

cat > src/boostprompt/agents/discovery.py << 'EOF'
"""
Agente de Discovery: conduz as 30-50 perguntas estruturadas.
"""
from .base import BaseAgent


class DiscoveryAgent(BaseAgent):
    name = "discovery"
    description = "Conduz entrevista de discovery com perguntas estruturadas"

    async def execute(self, state: dict) -> dict:
        # Implementação futura
        return state
EOF

cat > src/boostprompt/agents/architecture.py << 'EOF'
"""
Agente de Arquitetura: foca em arquitetura, stack, integrações, dados.
"""
from .base import BaseAgent


class ArchitectureAgent(BaseAgent):
    name = "architecture"
    description = "Especialista em arquitetura e stack tecnológica"

    async def execute(self, state: dict) -> dict:
        return state
EOF

cat > src/boostprompt/agents/security.py << 'EOF'
"""
Agente de Segurança: segurança, compliance, LGPD, auditoria.
"""
from .base import BaseAgent


class SecurityAgent(BaseAgent):
    name = "security"
    description = "Especialista em segurança e compliance"

    async def execute(self, state: dict) -> dict:
        return state
EOF

cat > src/boostprompt/agents/delivery.py << 'EOF'
"""
Agente de Delivery: CI/CD, deploy, operação, monitoramento.
"""
from .base import BaseAgent


class DeliveryAgent(BaseAgent):
    name = "delivery"
    description = "Especialista em entrega e operação"

    async def execute(self, state: dict) -> dict:
        return state
EOF

cat > src/boostprompt/agents/synthesis.py << 'EOF'
"""
Agente de Synthesis: consolida tudo no Markdown final.
"""
from .base import BaseAgent


class SynthesisAgent(BaseAgent):
    name = "synthesis"
    description = "Consolida o discovery no documento Markdown final"

    async def execute(self, state: dict) -> dict:
        return state
EOF

cat > src/boostprompt/agents/memory.py << 'EOF'
"""
Agente de Memory: gerencia persistência e recuperação no DuckDB.
"""
from .base import BaseAgent


class MemoryAgent(BaseAgent):
    name = "memory"
    description = "Gerencia memória e persistência das sessões"

    async def execute(self, state: dict) -> dict:
        return state
EOF

# --- Graph ---
cat > src/boostprompt/graph/workflow.py << 'EOF'
"""
Definição do grafo de fluxo com LangGraph.
Orquestra os agentes em uma state machine.
"""
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Any


class AgentState(TypedDict):
    """Estado compartilhado entre os agentes."""
    messages: list[dict[str, Any]]
    context: dict[str, Any]
    current_phase: str
    questions_count: int
    decisions: list[dict[str, Any]]
    session_id: str | None


def create_workflow() -> StateGraph:
    """Cria e retorna o grafo de workflow."""
    # Implementação futura
    graph = StateGraph(AgentState)
    graph.add_node("start", lambda state: state)
    graph.add_edge(START, "start")
    graph.add_edge("start", END)
    return graph
EOF

# --- Memory ---
cat > src/boostprompt/memory/duckdb_store.py << 'EOF'
"""
Camada de persistência com DuckDB.
Gerencia sessões, mensagens, contexto e decisões.
"""
import duckdb
from pathlib import Path
from datetime import datetime
import uuid
import json


class DuckDBStore:
    """Armazenamento persistente com DuckDB."""

    def __init__(self, db_path: str = "data/boostprompt.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self):
        """Inicializa o schema do banco."""
        # Sessions
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                codigo TEXT UNIQUE,
                nome TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                status TEXT
            )
        """)

        # Messages
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # Context Snapshots
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS context_snapshots (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                snapshot_data TEXT,
                questions_count INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # Decisions
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                category TEXT,
                decision TEXT,
                alternatives TEXT,
                tradeoffs TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

    def create_session(self, nome: str) -> tuple[str, str]:
        """Cria uma nova sessão e retorna (session_id, codigo)."""
        session_id = str(uuid.uuid4())
        codigo = f"BP-{datetime.now().strftime('%Y')}-{self._get_next_code()}"
        now = datetime.now()

        self.conn.execute("""
            INSERT INTO sessions (id, codigo, nome, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, [session_id, codigo, nome, now, now])

        return session_id, codigo

    def _get_next_code(self) -> str:
        """Obtém o próximo número sequencial para o código."""
        result = self.conn.execute("""
            SELECT COUNT(*) FROM sessions
        """).fetchone()
        return f"{result[0]:03d}"

    def save_message(self, session_id: str, role: str, content: str):
        """Salva uma mensagem no histórico."""
        msg_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO messages (id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [msg_id, session_id, role, content, datetime.now()])

        self.conn.execute("""
            UPDATE sessions SET updated_at = ? WHERE id = ?
        """, [datetime.now(), session_id])

    def get_messages(self, session_id: str) -> list[dict]:
        """Recupera todas as mensagens de uma sessão."""
        result = self.conn.execute("""
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, [session_id])

        return [{"role": row[0], "content": row[1]} for row in result.fetchall()]

    def get_messages_summary(self, session_id: str, limit: int = 10) -> list[dict]:
        """Recupera resumo das Ãltimas mensagens (para contexto reduzido)."""
        result = self.conn.execute("""
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, [session_id, limit])

        return [{"role": row[0], "content": row[1]} for row in result.fetchall()]

    def save_context_snapshot(self, session_id: str, context: dict, questions_count: int):
        """Salva um snapshot do contexto atual."""
        snapshot_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO context_snapshots (id, session_id, snapshot_data, questions_count, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [snapshot_id, session_id, json.dumps(context), questions_count, datetime.now()])

    def get_latest_context(self, session_id: str) -> dict | None:
        """Recupera o Ãltimo snapshot de contexto."""
        result = self.conn.execute("""
            SELECT snapshot_data FROM context_snapshots
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, [session_id]).fetchone()

        if result:
            return json.loads(result[0])
        return None

    def save_decision(self, session_id: str, category: str, decision: str,
                      alternatives: list, tradeoffs: str):
        """Salva uma decisão tomada."""
        decision_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO decisions (id, session_id, category, decision, alternatives, tradeoffs, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [decision_id, session_id, category, decision,
              json.dumps(alternatives), tradeoffs, datetime.now()])

    def get_decisions(self, session_id: str) -> list[dict]:
        """Recupera todas as decisões de uma sessão."""
        result = self.conn.execute("""
            SELECT category, decision, alternatives, tradeoffs FROM decisions
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, [session_id])

        return [
            {
                "category": row[0],
                "decision": row[1],
                "alternatives": json.loads(row[2]),
                "tradeoffs": row[3]
            }
            for row in result.fetchall()
        ]

    def list_sessions(self) -> list[dict]:
        """Lista todas as sessões."""
        result = self.conn.execute("""
            SELECT id, codigo, nome, created_at, updated_at, status FROM sessions
            ORDER BY updated_at DESC
        """)

        return [
            {
                "id": row[0],
                "codigo": row[1],
                "nome": row[2],
                "created_at": row[3],
                "updated_at": row[4],
                "status": row[5]
            }
            for row in result.fetchall()
        ]

    def get_session(self, session_id: str) -> dict | None:
        """Obtém detalhes de uma sessão especìfica."""
        result = self.conn.execute("""
            SELECT id, codigo, nome, created_at, updated_at, status FROM sessions
            WHERE id = ?
        """, [session_id]).fetchone()

        if result:
            return {
                "id": result[0],
                "codigo": result[1],
                "nome": result[2],
                "created_at": result[3],
                "updated_at": result[4],
                "status": result[5]
            }
        return None

    def delete_session(self, session_id: str):
        """Deleta uma sessão e todos os dados relacionados."""
        self.conn.execute("DELETE FROM decisions WHERE session_id = ?", [session_id])
        self.conn.execute("DELETE FROM context_snapshots WHERE session_id = ?", [session_id])
        self.conn.execute("DELETE FROM messages WHERE session_id = ?", [session_id])
        self.conn.execute("DELETE FROM sessions WHERE id = ?", [session_id])

    def close(self):
        """Fecha a conexão com o banco."""
        self.conn.close()
EOF

# --- Models ---
cat > src/boostprompt/models/schemas.py << 'EOF'
"""
Modelos Pydantic para validação de dados.
"""
from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class Session(BaseModel):
    """Modelo de uma sessão."""
    id: str
    codigo: str
    nome: str
    created_at: datetime
    updated_at: datetime
    status: str


class Message(BaseModel):
    """Modelo de uma mensagem."""
    role: str
    content: str


class Decision(BaseModel):
    """Modelo de uma decisão tomada."""
    category: str
    decision: str
    alternatives: list[dict[str, Any]]
    tradeoffs: str


class ContextState(BaseModel):
    """Modelo do estado de contexto acumulado."""
    nome_projeto: str = ""
    necessidade: str = ""
    problema: str = ""
    objetivo: str = ""
    dominio: str = ""
    tipo_solucao: str = ""
    usuarios: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    plataformas: list[str] = Field(default_factory=list)
    restricoes: list[str] = Field(default_factory=list)
    requisitos_funcionais: list[str] = Field(default_factory=list)
    requisitos_nao_funcionais: list[str] = Field(default_factory=list)
    integracoes: list[str] = Field(default_factory=list)
    dados: list[str] = Field(default_factory=list)
    arquitetura: list[str] = Field(default_factory=list)
    seguranca: list[str] = Field(default_factory=list)
    operacao: list[str] = Field(default_factory=list)
    entrega: list[str] = Field(default_factory=list)
    riscos: list[str] = Field(default_factory=list)
    premissas: list[str] = Field(default_factory=list)
    decisoes: list[dict[str, Any]] = Field(default_factory=list)
    pendencias: list[str] = Field(default_factory=list)
EOF

# --- Prompts ---
cat > src/boostprompt/prompts/discovery.py << 'EOF'
"""
Prompts para o agente de Discovery.
"""

DISCOVERY_INTRO = """Olá! Eu sou o BoostPrompt e vou te ajudar a transformar sua necessidade em um escopo completo, atualizado e implementável.

Vou conduzir uma entrevista estruturada com no mìnimo 30 e no máximo 50 perguntas. Em cada etapa, vou trazer alternativas, explicar trade-offs e recomendar a melhor direção com base no seu contexto e, quando disponìvel, em referências atuais obtidas por pesquisa.

Para começar, descreva a necessidade, ideia ou problema que você quer transformar em solução."""

QUESTION_TEMPLATE = """### Pergunta {number} — {category}

**Por que esta pergunta importa:**  
{why_it_matters}

**Alternativas:**

{alternatives}

**Recomendação da IA:**  
{ai_recommendation}

**Como responder:**  
{how_to_respond}"""
EOF

cat > src/boostprompt/prompts/synthesis.py << 'EOF'
"""
Prompts para o agente de Synthesis.
"""

SYNTHESIS_SYSTEM_PROMPT = """Você ÃÂ© o agente de Synthesis do BoostPrompt.
Sua função ÃÂ© consolidar todo o contexto coletado durante o discovery em um Ãnico documento Markdown completo e implementável.

O documento deve seguir exatamente a estrutura definida na skill original, incluindo:
- Resumo executivo
- Problema e contexto
- Objetivos de negócio
- Público-alvo, usuários e stakeholders
- Premissas e restrições
- Requisitos funcionais
- Requisitos não funcionais
- Arquitetura recomendada
- Stack tecnológica sugerida
- Dados, integrações e fluxos
- Segurança, privacidade e compliance
- Estratégia de entrega e operação
- Observabilidade, suporte e evolução
- Riscos, trade-offs e mitigação
- Roadmap sugerido
- Decisões consolidadas
- Plano de execução
- Critérios de aceite
- Estratégia de validação
- Pendências para execução
- Referências consultadas
- Prompt mestre para implementação

Não invente informações. Use apenas o que foi coletado durante o discovery."""
EOF

# --- Utils ---
cat > src/boostprompt/utils/helpers.py << 'EOF'
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
EOF

# --- CLI (placeholder inicial) ---
cat > src/boostprompt/cli/app.py << 'EOF'
"""
Aplicação CLI com Textual (TUI).
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container
from textual.binding import Binding


class BoostPromptApp(App):
    """Aplicação principal do BoostPrompt CLI."""

    CSS = """
    Container {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Sair", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("# BoostPrompt CLI\n\nSelecione uma opção:"),
        )
        yield Footer()


if __name__ == "__main__":
    app = BoostPromptApp()
    app.run()
EOF

# --- Main package init ---
cat > src/boostprompt/__init__.py << 'EOF'
"""
BoostPrompt CLI - Aplicação de discovery com LangChain, LangGraph e Pydantic AI.
"""
__version__ = "0.1.0"
EOF

# =============================================================================
# 4. Criar pyproject.toml com UV
# =============================================================================

echo "📦 Criando pyproject.toml..."

cat > pyproject.toml << 'EOF'
[project]
name = "boostprompt"
version = "0.1.0"
description = "CLI de discovery com LangChain, LangGraph e Pydantic AI"
readme = "README.md"
requires-python = ">=3.11"
authors = [
    {name = "Airton Lira", email = "airton@example.com"}
]
dependencies = [
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "pydantic>=2.0.0",
    "pydantic-ai>=0.0.10",
    "duckdb>=1.0.0",
    "textual>=0.50.0",
    "litellm>=1.40.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[project.scripts]
boostprompt = "boostprompt.cli.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/boostprompt"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
EOF

# =============================================================================
# 5. Criar .env.example
# =============================================================================

echo "🔐 Criando .env.example..."

cat > .env.example << 'EOF'
# Configurações de LLM via LiteLLM
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Ou Anthropic
# LLM_PROVIDER=anthropic
# LLM_MODEL=claude-3-5-sonnet-20241022
# ANTHROPIC_API_KEY=sk-ant-...

# Ou outro provedor suportado pelo LiteLLM
# LLM_PROVIDER=...
# LLM_MODEL=...
# API_KEY=...

# Caminho do banco DuckDB (opcional, default: data/boostprompt.db)
DUCKDB_PATH=data/boostprompt.db
EOF

# =============================================================================
# 6. Criar .gitignore
# =============================================================================

echo "🙈 Criando .gitignore..."

cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Environment
.env
.env.local

# Database
data/*.db
data/*.db.*

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db
EOF

# =============================================================================
# 7. Criar README.md inicial
# =============================================================================

echo "📖 Criando README.md..."

cat > README.md << 'EOF'
# BoostPrompt CLI

Aplicativo CLI de discovery com LangChain, LangGraph e Pydantic AI.

## Instalação

```bash
# Instalar UV (se ainda não tiver)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependências
uv sync

# Ativar ambiente virtual
source .venv/bin/activate
```

## Uso

```bash
# Iniciar a aplicação CLI
boostprompt
```

## Desenvolvimento

```bash
# Rodar testes
uv run pytest

# Formatar código
uv run ruff format .

# Type checking
uv run mypy src/
```

## Estrutura

```
src/boostprompt/
â»¿â»¿ agents/       # Agentes especializados (Pydantic AI)
â»¿â»¿ graph/        # Orquestração com LangGraph
â»¿â»¿ memory/       # Persistência com DuckDB
â»¿â»¿ models/       # Modelos Pydantic
â»¿â»¿ prompts/      # Templates de prompt
â»¿â»¿ utils/        # Utilitários
â»¿â»¿ cli/          # Interface CLI (Textual)
```

## Skills

A skill original (para uso no Claude/CodeX) permanece em `SKILL.md`.
EOF

# =============================================================================
# 8. Criar arquivo de entry point para o script CLI
# =============================================================================

echo "🚀 Criando entry point da CLI..."

cat > src/boostprompt/cli/__main__.py << 'EOF'
"""
Entry point para execução como módulo: python -m boostprompt.cli
"""
from .app import main


def main():
    """Função principal da CLI."""
    from textual.app import App
    from textual.widgets import Header, Footer, Static, Button
    from textual.containers import Container
    from textual.screen import Screen
    from textual.binding import Binding

    class MainMenu(Screen):
        BINDINGS = [Binding("q", "quit", "Sair")]

        def compose(self):
            yield Header()
            yield Static("# BoostPrompt CLI\n\nEscolha uma opção:")
            yield Button("Nova Sessão", id="new_session", variant="primary")
            yield Button("Listar Sessões", id="list_sessions")
            yield Button("Retomar Sessão", id="resume_session")
            yield Button("Sair", id="quit", variant="error")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed):
            if event.button.id == "quit":
                self.app.exit()
            elif event.button.id == "new_session":
                self.app.notify("Funcionalidade em desenvolvimento...")
            elif event.button.id == "list_sessions":
                self.app.notify("Funcionalidade em desenvolvimento...")
            elif event.button.id == "resume_session":
                self.app.notify("Funcionalidade em desenvolvimento...")

    class BoostPromptApp(App):
        CSS = """
        Button {
            margin: 1;
        }
        Static {
            content-align: center middle;
            height: 100%;
        }
        """
        BINDINGS = [Binding("q", "quit", "Sair")]

        def on_mount(self):
            self.push_screen(MainMenu())

    app = BoostPromptApp()
    app.run()


if __name__ == "__main__":
    main()
EOF

# Atualizar app.py para importar corretamente
cat > src/boostprompt/cli/app.py << 'EOF'
"""
Módulo principal da CLI.
"""
from .__main__ import main

__all__ = ["main"]
EOF

# =============================================================================
# 9. Criar pasta para skills (preservando a existente)
# =============================================================================

echo "💾 Criando pasta de skills..."

mkdir -p skills

# Se SKILL.md existir na raiz, mover para skills/
if [ -f "SKILL.md" ]; then
    echo "📋 Movendo SKILL.md para skills/..."
    mv SKILL.md skills/
fi

# Criar README na pasta de skills
cat > skills/README.md << 'EOF'
# Skills do BoostPrompt

Esta pasta contém as skills originais para uso direto no Claude/CodeX.

## Arquivos

- `SKILL.md` - Skill principal de discovery (30-50 perguntas)

## Uso

Copie o conteúdo da skill e cole no Claude/CodeX como um harness personalizado.
EOF

# =============================================================================
# 10. Mensagem final
# =============================================================================

echo ""
echo "¬¡ Setup concluìdo com sucesso!"
echo ""
echo "Próximos passos:"
echo "  1. Revise a estrutura criada: tree -L 3"
echo "  2. Instale as dependências: uv sync"
echo "  3. Ative o ambiente: source .venv/bin/activate"
echo "  4. Configure suas chaves: cp .env.example .env"
echo "  5. Teste a CLI: uv run python -m boostprompt.cli"
echo ""
echo "A skill original foi movida para skills/SKILL.md"
echo ""