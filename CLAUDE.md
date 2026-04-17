# Cosmetic Complaint Intelligence System (CCIS)

## Visão geral do projeto
Sistema de inteligência para monitoramento, extração, classificação e priorização de reclamações e avaliações públicas sobre **cosméticos artesanais** no Brasil. Utiliza exclusivamente **fontes legais, APIs oficiais e dados abertos governamentais**.

## Princípios invioláveis
- **ZERO scraping não autorizado** — apenas APIs oficiais e dados abertos
- **Anonimização antes de armazenar** — spaCy NER + regex para remover dados pessoais
- **LGPD compliance-by-design** — base legal: legítimo interesse (Art. 7º, IX) com RIPD
- **Respeito a rate limits** — cada API tem limites documentados no código

## Stack tecnológico
- **Linguagem**: Python 3.11+
- **APIs HTTP**: httpx (async) + requests
- **NLP**: spaCy (pt_core_news_lg), sentence-transformers
- **ML**: scikit-learn (TF-IDF + SVM), HDBSCAN
- **Classificação**: Claude API (Batch), Pydantic (validação de schema)
- **Banco**: PostgreSQL + pgvector
- **Orquestração**: Apache Airflow
- **Dashboard**: Streamlit (MVP) → Metabase (produção)

## Fontes de dados (todas legais)

### Camada 1 — Dados abertos (sem barreiras)
| Fonte | Acesso | Notas |
|-------|--------|-------|
| Consumidor.gov.br | CSV download + API REST | dados.mj.gov.br/dataset/reclamacoes-do-consumidor-gov-br |
| Notivisa / Anvisa | Export dados abertos | Eventos adversos + queixas técnicas de cosméticos |
| DataJud / CNJ | API pública (chave gratuita) | api-publica.datajud.cnj.jus.br — processos judiciais |
| Anvisa Registros | CSV Portal Dados Abertos | Cosméticos registrados no Brasil (cruzamento) |
| DOU / Imprensa Nacional | API pública | Alertas, recalls e interdições |

### Camada 2 — APIs oficiais (autenticação)
| Fonte | API | Auth | Rate limit |
|-------|-----|------|------------|
| Mercado Livre | /reviews/item/{ID} | OAuth 2.0 | 1500 req/min |
| Google Places | Places API | API Key | Tier gratuito até $200/mês |
| Reddit | reddit.com/dev/api | OAuth 2.0 | 100 req/min |
| YouTube | Data API v3 | API Key | 10.000 units/dia |
| PubMed | E-utilities | Nenhum | 3 req/s (sem key), 10 req/s (com key) |

### Camada 3 — Coleta complementar
| Fonte | Método |
|-------|--------|
| Formulário voluntário | Google Forms / Typeform (consentimento LGPD) |
| Procons estaduais | Portais estaduais + LAI |

### Fontes DESCARTADAS (e por quê)
- **Reclame Aqui**: sem API pública, termos proíbem scraping, proteção anti-bot
- **Shopee**: SPA com CAPTCHA agressivo, API só para sellers
- **JusBrasil**: paywall para conteúdo completo → substituído por DataJud/CNJ
- **Magazine Luiza**: sem API de leitura de reviews, termos restritivos

## Estrutura do projeto
```
ccis-project/
├── CLAUDE.md                  # Este arquivo (instruções do projeto)
├── README.md                  # Documentação pública
├── pyproject.toml             # Configuração do projeto Python
├── .env.example               # Template de variáveis de ambiente
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py        # Configurações centralizadas (Pydantic Settings)
│   ├── ingestion/             # Fase 1 — Coleta de dados
│   │   ├── __init__.py
│   │   ├── base.py            # Classe base para ingestores
│   │   ├── consumidor_gov.py  # Consumidor.gov.br (CSV)
│   │   ├── notivisa.py        # Notivisa/Anvisa (dados abertos)
│   │   ├── datajud.py         # DataJud/CNJ (API pública)
│   │   ├── mercadolivre.py    # Mercado Livre (API oficial)
│   │   ├── google_places.py   # Google Places API
│   │   ├── reddit.py          # Reddit API
│   │   ├── youtube.py         # YouTube Data API
│   │   ├── pubmed.py          # PubMed (E-utilities)
│   │   ├── dou.py             # DOU / Imprensa Nacional
│   │   └── anvisa_registros.py # Base de registros Anvisa
│   ├── anonymization/         # Fase 2 — Anonimização LGPD
│   │   ├── __init__.py
│   │   ├── anonymizer.py      # Pipeline de anonimização
│   │   ├── ner_detector.py    # Detecção de entidades (spaCy)
│   │   ├── regex_patterns.py  # Padrões brasileiros (CPF, tel, etc.)
│   │   └── audit_log.py       # Log de auditoria
│   ├── prefilter/             # Fase 3 — Pré-filtro NLP
│   │   ├── __init__.py
│   │   ├── classifier.py      # TF-IDF + SVM (relevante/irrelevante)
│   │   ├── artisanal_detector.py # Detecção de cosméticos artesanais
│   │   └── keywords.py        # Listas de inclusão/exclusão
│   ├── classification/        # Fase 4 — Classificação (Claude API)
│   │   ├── __init__.py
│   │   ├── batch_classifier.py # Envio em lotes para Claude API
│   │   ├── prompts.py         # Prompts otimizados
│   │   └── schemas.py         # Schemas Pydantic de saída
│   ├── enrichment/            # Fase 5 — Enriquecimento
│   │   ├── __init__.py
│   │   ├── regulatory_cross.py # Cruzamento com registros Anvisa
│   │   ├── ingredient_check.py # Verificação de ingredientes restritos
│   │   ├── clustering.py      # HDBSCAN sobre embeddings
│   │   ├── risk_score.py      # Score de risco composto
│   │   └── trend_detection.py # Detecção de tendências temporais
│   ├── storage/               # Fase 6 — Armazenamento
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── database.py        # Conexão PostgreSQL + pgvector
│   │   └── repositories.py    # Repositórios de acesso a dados
│   ├── alerts/                # Sistema de alertas
│   │   ├── __init__.py
│   │   ├── alert_engine.py    # Motor de alertas por threshold
│   │   └── notifiers.py       # E-mail, webhook, Slack
│   └── dashboard/             # Dashboard Streamlit
│       ├── __init__.py
│       ├── app.py             # Aplicação principal
│       ├── pages/
│       │   ├── overview.py
│       │   ├── risk_ranking.py
│       │   ├── trends.py
│       │   └── alerts.py
│       └── components/
├── dags/                      # DAGs do Apache Airflow
│   ├── dag_consumidor_gov.py
│   ├── dag_notivisa.py
│   ├── dag_mercadolivre.py
│   ├── dag_datajud.py
│   └── dag_daily_pipeline.py
├── tests/
│   ├── __init__.py
│   ├── test_ingestion/
│   ├── test_anonymization/
│   ├── test_prefilter/
│   ├── test_classification/
│   └── test_enrichment/
├── scripts/
│   ├── setup_db.py            # Inicialização do banco
│   ├── train_prefilter.py     # Treinamento do pré-filtro
│   └── download_spacy_model.py
├── data/
│   ├── raw/                   # Dados brutos baixados
│   ├── anonymized/            # Dados após anonimização
│   ├── classified/            # Dados após classificação
│   └── reference/             # Listas de referência (ingredientes, keywords)
├── docs/
│   ├── ULTRAPLAN_v2.docx      # Planejamento executivo completo
│   ├── LGPD_RIPD.md           # Relatório de Impacto à Proteção de Dados
│   ├── API_DOCS.md            # Documentação de cada API utilizada
│   └── ARCHITECTURE.md        # Diagrama de arquitetura
└── docker/
    ├── Dockerfile
    ├── docker-compose.yml     # PostgreSQL + Airflow + App
    └── .env.docker
```

## Categorias de classificação
- **Segurança** (peso 5): eventos adversos — reação alérgica, irritação cutânea, vermelhidão, coceira, descamação, queimadura, edema, queda de cabelo, ardência, intoxicação, bolhas, urticária, dermatite
- **Qualidade** (peso 2): defeitos no produto — partículas estranhas, cor/cheiro alterado, separação de fases, mofo, produto vencido, frasco quebrado/vazando, volume/peso menor, textura diferente, rótulo ausente
- **Eficácia** (peso 3): não cumpre finalidade — sem efeito, resultado diferente do prometido, propaganda enganosa, hidratante que não hidrata, filtro solar que não protege
- **Comercial** (peso 0, excluído da análise): problemas comerciais/logísticos — atraso na entrega, cobrança indevida, divergência de preço, negativação, reembolso, atendimento, frete

## Escala de severidade (1-5)
1. Informativo — observação sem impacto
2. Baixo — insatisfação leve
3. Médio — problema funcional moderado
4. Alto — reação adversa leve/moderada → ALERTA
5. Crítico — dano à saúde → ALERTA URGENTE

## Score de risco
`Score = Σ (peso_categoria × severidade × frequência_relativa)`
- Score ≥ 15: Alerta vermelho (notificação imediata)
- Score 8-14: Alerta amarelo (monitoramento ativo)
- Score < 8: Monitoramento padrão

## Contexto regulatório
- **Lei 15.154/2025**: cosméticos artesanais dispensados de registro Anvisa (vigência: 30/08/2025)
- **RDC 894/2024**: cosmetovigilância obrigatória, notificação de eventos adversos graves
- **RDC 907/2024**: regulação consolidada, controle microbiológico, rotulagem bilíngue
- **RDC 529/2021**: lista de ingredientes proibidos (usar para cruzamento)
- **ANPD Radar Tecnológico nº 3**: scraping = tratamento de dados pessoais sob LGPD

## Convenções de código
- Python 3.11+ com type hints obrigatórios
- Formatação: ruff (lint + format)
- Testes: pytest com fixtures compartilhadas
- Docstrings: Google style
- Commits: Conventional Commits (feat:, fix:, docs:, etc.)
- Variáveis de ambiente: Pydantic Settings (nunca hardcoded)
- Logging: structlog (JSON structured logging)
- Async: httpx para todas as chamadas HTTP

## Roadmap de implementação
### Fase 1 — MVP (Semanas 1-4)
Consumidor.gov.br + Notivisa + Anonimização + Classificação Claude + PostgreSQL + Streamlit básico

### Fase 2 — Expansão (Semanas 5-8)
Mercado Livre API + DataJud + Google Places + Score de risco + Alertas

### Fase 3 — Redes sociais (Semanas 9-12)
Reddit + YouTube + DOU + HDBSCAN + Airflow + Metabase

### Fase 4 — Inteligência avançada (Semanas 13+)
Fine-tuning local + Tendências temporais + Formulário voluntário + RIPD completo
