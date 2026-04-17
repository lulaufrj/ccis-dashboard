# Guia de Deploy — Streamlit Community Cloud

Publica o dashboard CCIS numa URL pública gratuita (ex:
`https://ccis-dashboard.streamlit.app`) para enviar a colaboradores.

## Pré-requisitos

- Conta no GitHub (gratuita)
- Conta no [Streamlit Community Cloud](https://share.streamlit.io) (login com GitHub)

## O que já foi preparado no repo

| Arquivo | Função |
|---------|--------|
| `requirements.txt` | Dependências mínimas (streamlit + pandas + plotly) |
| `.streamlit/config.toml` | Tema e configurações do servidor |
| `scripts/prepare_deploy.py` | Gera JSON enxuto (~100 KB, só artesanais) |
| `data/classified/classificados_deploy.json` | Subset público (114 registros) |
| `.gitignore` | Permite apenas o JSON de deploy, bloqueia os dados brutos |

## Passo 1 — Regenerar o JSON de deploy (sempre que reprocessar dados)

```bash
python scripts/prepare_deploy.py
```

Aplica o filtro industrial e salva em `data/classified/classificados_deploy.json`.
Esse é o único JSON que vai pro GitHub.

## Passo 2 — Subir no GitHub

Se ainda não inicializou o repositório:

```bash
git init
git add .
git commit -m "feat: dashboard CCIS pronto para deploy"
git branch -M main
git remote add origin https://github.com/<seu-usuário>/ccis-dashboard.git
git push -u origin main
```

**O repo pode ser privado** — o Streamlit Cloud acessa mesmo assim.

⚠️ Antes do `git add`, confirme que o `.env` (com `ANTHROPIC_API_KEY`) está
bloqueado pelo `.gitignore`. Rode: `git status | grep env` — não deve aparecer.

## Passo 3 — Deploy no Streamlit Cloud

1. Acesse https://share.streamlit.io
2. Clique em **"New app"**
3. Preencha:
   - **Repository:** `<seu-usuário>/ccis-dashboard`
   - **Branch:** `main`
   - **Main file path:** `src/dashboard/app.py`
   - **App URL:** escolha um subdomínio (ex: `ccis-dashboard`)
4. Clique em **"Deploy"**

O primeiro build demora ~2 minutos. Depois, cada `git push` redeploya
automaticamente.

## Passo 4 — Compartilhar

A URL gerada (ex: `https://ccis-dashboard.streamlit.app`) já é pública.
Envie aos colaboradores.

> Se quiser restringir quem acessa, nas configurações do app marque
> **"Viewer access"** → adicione os e-mails permitidos. Eles farão login
> com Google/GitHub para abrir o dashboard.

## Atualizar o dashboard

Sempre que reprocessar dados:

```bash
python scripts/prepare_deploy.py          # regenera JSON enxuto
git add data/classified/classificados_deploy.json
git commit -m "data: atualização classificação"
git push
```

O Streamlit Cloud detecta e redeploya automaticamente.

## Troubleshooting

**"ModuleNotFoundError: No module named 'src'"**
→ O caminho raiz não foi resolvido. Verifique que `src/__init__.py` existe.

**"Nenhum dado classificado encontrado"**
→ O `classificados_deploy.json` não foi commitado. Rode:
```bash
git check-ignore data/classified/classificados_deploy.json
```
Se retornar algo, o gitignore ainda está bloqueando — revise a exceção.

**App muito lento**
→ Streamlit Cloud tier gratuito dorme após 7 dias sem acesso. Primeiro
acesso demora ~30s para "acordar". Depois fica rápido.
