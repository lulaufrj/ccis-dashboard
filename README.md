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
