#!/usr/bin/env bash
# ============================================================
# CCIS Project — Setup Script
# Cosmetic Complaint Intelligence System
# Execute: chmod +x setup.sh && ./setup.sh
# ============================================================

set -euo pipefail

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Cosmetic Complaint Intelligence System — Setup         ║"
echo "║  Inicializando estrutura do projeto...                  ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ─── Criar estrutura de diretórios ───────────────────────────
echo ""
echo "📁 Criando estrutura de diretórios..."

dirs=(
  "src/config"
  "src/ingestion"
  "src/anonymization"
  "src/prefilter"
  "src/classification"
  "src/enrichment"
  "src/storage"
  "src/alerts"
  "src/dashboard/pages"
  "src/dashboard/components"
  "dags"
  "tests/test_ingestion"
  "tests/test_anonymization"
  "tests/test_prefilter"
  "tests/test_classification"
  "tests/test_enrichment"
  "scripts"
  "data/raw"
  "data/anonymized"
  "data/classified"
  "data/reference"
  "docs"
  "docker"
)

for dir in "${dirs[@]}"; do
  mkdir -p "$dir"
  # Criar __init__.py em diretórios Python
  if [[ "$dir" == src/* ]] || [[ "$dir" == tests/* ]]; then
    touch "$dir/__init__.py"
  fi
done

# Init files na raiz dos pacotes
touch src/__init__.py
touch tests/__init__.py

echo "   ✅ Estrutura criada (${#dirs[@]} diretórios)"

# ─── Criar pyproject.toml ───────────────────────────────────
echo ""
echo "📦 Criando pyproject.toml..."

cat > pyproject.toml << 'PYPROJECT'
[project]
name = "ccis"
version = "0.1.0"
description = "Cosmetic Complaint Intelligence System — Monitoramento de reclamações sobre cosméticos artesanais"
requires-python = ">=3.11"
dependencies = [
    # HTTP & APIs
    "httpx>=0.27",
    "requests>=2.31",
    # NLP & ML
    "spacy>=3.7",
    "sentence-transformers>=2.2",
    "scikit-learn>=1.4",
    "hdbscan>=0.8",
    # Data
    "pandas>=2.2",
    "numpy>=1.26",
    # Database
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "pgvector>=0.2",
    "alembic>=1.13",
    # Claude API
    "anthropic>=0.40",
    # Validation
    "pydantic>=2.6",
    "pydantic-settings>=2.1",
    # Dashboard
    "streamlit>=1.30",
    "plotly>=5.18",
    # Utilities
    "structlog>=24.1",
    "python-dotenv>=1.0",
    "rich>=13.7",
    "tenacity>=8.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.4",
    "mypy>=1.8",
    "pre-commit>=3.6",
]
airflow = [
    "apache-airflow>=2.8",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.11"
strict = true
PYPROJECT

echo "   ✅ pyproject.toml criado"

# ─── Criar .env.example ─────────────────────────────────────
echo ""
echo "🔑 Criando .env.example..."

cat > .env.example << 'ENVFILE'
# ============================================================
# CCIS — Variáveis de ambiente
# Copie para .env e preencha com seus valores
# ============================================================

# --- Claude API ---
ANTHROPIC_API_KEY=sk-ant-...

# --- PostgreSQL ---
DATABASE_URL=postgresql://ccis:ccis_password@localhost:5432/ccis_db

# --- Mercado Livre ---
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_ACCESS_TOKEN=

# --- Google Cloud (Places API + YouTube Data API) ---
GOOGLE_API_KEY=

# --- Reddit ---
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=ccis/1.0

# --- DataJud / CNJ ---
DATAJUD_API_KEY=

# --- PubMed ---
PUBMED_API_KEY=

# --- Alertas ---
ALERT_EMAIL_TO=
SENDGRID_API_KEY=
SLACK_WEBHOOK_URL=

# --- Configurações gerais ---
LOG_LEVEL=INFO
ENVIRONMENT=development
ENVFILE

echo "   ✅ .env.example criado"

# ─── Criar .gitignore ───────────────────────────────────────
echo ""
echo "🚫 Criando .gitignore..."

cat > .gitignore << 'GITIGNORE'
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Environment
.env
.venv/
venv/

# Data (nunca commitar dados brutos)
data/raw/
data/anonymized/
data/classified/
*.csv
*.json.gz

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Docker
docker/.env.docker

# Airflow
airflow.db
airflow-webserver.pid
logs/

# Pytest
.pytest_cache/
htmlcov/
.coverage
GITIGNORE

echo "   ✅ .gitignore criado"

# ─── Criar README.md ────────────────────────────────────────
echo ""
echo "📝 Criando README.md..."

cat > README.md << 'README'
# 🧴 Cosmetic Complaint Intelligence System (CCIS)

Sistema de inteligência para monitoramento de reclamações sobre cosméticos artesanais no Brasil.

## Características

- **15 fontes de dados legais** (dados abertos + APIs oficiais)
- **Zero scraping não autorizado** — compliance total com LGPD e termos de uso
- **Classificação por IA** — Claude API para categorização semântica
- **Cosmetovigilância** — alinhado com RDC 894/2024 e Lei 15.154/2025
- **Score de risco composto** — priorização automática de alertas

## Quick Start

```bash
# 1. Clonar e entrar no projeto
cd ccis-project

# 2. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instalar dependências
pip install -e ".[dev]"

# 4. Baixar modelo spaCy
python -m spacy download pt_core_news_lg

# 5. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves de API

# 6. Inicializar banco de dados
python scripts/setup_db.py

# 7. Executar MVP
streamlit run src/dashboard/app.py
```

## Documentação

- [ULTRAPLAN v2.0](docs/ULTRAPLAN_v2.docx) — Planejamento executivo completo
- [CLAUDE.md](CLAUDE.md) — Instruções do projeto para Claude Code
- [Arquitetura](docs/ARCHITECTURE.md) — Diagrama de arquitetura
- [LGPD RIPD](docs/LGPD_RIPD.md) — Relatório de impacto à proteção de dados

## Licença

Projeto privado — todos os direitos reservados.
README

echo "   ✅ README.md criado"

# ─── Copiar ULTRAPLAN ────────────────────────────────────────
if [ -f "../ultraplan.docx" ]; then
  cp ../ultraplan.docx docs/ULTRAPLAN_v2.docx
  echo ""
  echo "📄 ULTRAPLAN copiado para docs/"
fi

# ─── Inicializar Git ─────────────────────────────────────────
echo ""
echo "🔧 Inicializando repositório Git..."
git init -q
git add -A
git commit -q -m "feat: inicializar projeto CCIS — Cosmetic Complaint Intelligence System

- Estrutura de diretórios completa (6 fases do pipeline)
- CLAUDE.md com instruções do projeto para Claude Code
- pyproject.toml com todas as dependências
- .env.example com template de variáveis de ambiente
- README.md com quick start
- .gitignore configurado
- ULTRAPLAN v2.0 na pasta docs/"

echo "   ✅ Repositório inicializado com commit inicial"

# ─── Resumo ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✅ Projeto CCIS inicializado com sucesso!              ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║                                                        ║"
echo "║  Para usar com Claude Code:                            ║"
echo "║                                                        ║"
echo "║    cd ccis-project                                     ║"
echo "║    claude                                              ║"
echo "║                                                        ║"
echo "║  Claude Code vai ler o CLAUDE.md automaticamente       ║"
echo "║  e terá todo o contexto do projeto.                    ║"
echo "║                                                        ║"
echo "║  Próximo passo sugerido:                               ║"
echo "║  'Implemente a Fase 1 do MVP: ingestão do              ║"
echo "║   Consumidor.gov.br + anonimização + classificação'    ║"
echo "║                                                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
