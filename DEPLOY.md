# 🚀 Guia de Deploy — do zero à URL pública

**Público:** pessoas sem experiência com Git/GitHub.
**Resultado final:** uma URL como `https://ccis-dashboard.streamlit.app` que
você envia aos colaboradores. Atualização é um `git push` depois.

**Tempo total:** 15 minutos na primeira vez. 1 minuto nas seguintes.

---

## 📋 Nomes e valores que você vai usar

Anote estes nomes — eles vão aparecer várias vezes:

| O que | Valor sugerido |
|-------|---------------|
| Nome do repositório GitHub | `ccis-dashboard` |
| Visibilidade do repo | **Privado** (só quem você autoriza vê) |
| Branch principal | `main` |
| Arquivo principal do app | `src/dashboard/app.py` |
| Subdomínio Streamlit | `ccis-dashboard` (gera URL `ccis-dashboard.streamlit.app`) |

Se o nome `ccis-dashboard` já estiver em uso no Streamlit, tente
`ccis-cosmeticos`, `ccis-beta`, etc.

---

## ✅ Checagem inicial (faça na pasta do projeto)

Abra o **PowerShell** ou **Git Bash** na pasta do projeto. Se estiver no
Windows Explorer, clique com botão direito na pasta → **"Abrir no Terminal"**
ou **"Git Bash Here"**.

Cole os comandos abaixo para confirmar que tudo está instalado:

```bash
git --version
gh --version
python --version
```

Deve mostrar três versões (Git, GitHub CLI, Python). Se algum falhar, pare
aqui e me avise.

---

## PARTE 1 — Criar conta no GitHub (pule se já tem)

1. Acesse https://github.com/signup
2. Use o e-mail **professorluizufrj@gmail.com** (ou outro de sua preferência)
3. Escolha um nome de usuário curto (aparecerá na URL — ex: `luizufrj`)
4. Confirme e-mail

Anote seu **nome de usuário**. Vamos chamá-lo de `SEU_USUARIO` no resto do
guia.

---

## PARTE 2 — Conectar seu PC ao GitHub (1x só, para sempre)

Na linha de comando, rode:

```bash
gh auth login
```

Você verá um menu com perguntas. Responda assim (use ↑↓ e Enter):

```
? Where do you use GitHub?               → GitHub.com
? What is your preferred protocol?       → HTTPS
? Authenticate Git with your credentials? → Yes
? How would you like to authenticate?    → Login with a web browser
```

Vai aparecer um **código de 8 dígitos** (ex: `ABCD-1234`) e pedir para
copiar. Copie. O navegador vai abrir sozinho — cole o código, clique
"Continue" e "Authorize github". Volte ao terminal — deve dizer:

```
✓ Authentication complete.
✓ Logged in as SEU_USUARIO
```

**Pronto. Nunca mais precisa fazer isso.**

---

## PARTE 3 — Criar repositório e subir o código

Vamos criar o repo no GitHub **e** enviar os arquivos em uma sequência só.

### 3.1 — Preparar os dados para deploy

Antes do commit, regere o JSON enxuto (com só os 114 registros artesanais):

```bash
python scripts/prepare_deploy.py
```

Deve mostrar algo como:

```
Original: classificados.json — 43,948 registros (35.0 MB)
Deploy:   classificados_deploy.json — 114 registros (107 KB)
Redução: 99.7%
```

### 3.2 — Inicializar o git local

```bash
git init
git add .
git status
```

**⚠️ CRUCIAL:** olhe a saída de `git status`. Procure pelas palavras `.env`
ou `classificados.json` (sem o `_deploy`) na lista. **Se aparecerem, PARE** e
me avise antes de continuar — esses arquivos contêm dados sensíveis e não
podem ir pro GitHub. Se **NÃO** aparecem, está tudo certo.

### 3.3 — Fazer o primeiro commit

```bash
git commit -m "feat: dashboard CCIS pronto para deploy"
git branch -M main
```

### 3.4 — Criar o repo no GitHub e enviar (um comando só)

```bash
gh repo create ccis-dashboard --private --source=. --remote=origin --push
```

**O que esse comando faz, traduzido:**

- `gh repo create ccis-dashboard` → cria um repo chamado `ccis-dashboard`
- `--private` → privado (só você e quem você autorizar vê)
- `--source=.` → usa a pasta atual como fonte
- `--remote=origin` → conecta o git local ao GitHub
- `--push` → envia os arquivos

Você vai ver algo como:

```
✓ Created repository SEU_USUARIO/ccis-dashboard on GitHub
✓ Added remote https://github.com/SEU_USUARIO/ccis-dashboard.git
✓ Pushed commits to https://github.com/SEU_USUARIO/ccis-dashboard.git
```

**Confira abrindo a URL** `https://github.com/SEU_USUARIO/ccis-dashboard` no
navegador. Você deve ver as pastas `src/`, `data/`, `scripts/`, etc.

---

## PARTE 4 — Deploy no Streamlit Cloud

Agora o GitHub tem o código. Falta dizer ao Streamlit Cloud "publique isso
como um site".

### 4.1 — Login no Streamlit Cloud

1. Abra https://share.streamlit.io no navegador
2. Clique no botão azul **"Continue with GitHub"**
3. Autorize o acesso (tela do GitHub pedindo permissão) — clique em
   **"Authorize streamlit"**

### 4.2 — Criar o app

Você vai cair numa página chamada **"Workspace"** com um botão azul
**"Create app"** (ou "New app") no canto superior direito. Clique nele.

Vai aparecer uma pergunta:

> **Do you have an app?**
> Ele vai mostrar duas opções: "Yup, I have an app" e "Nope, create one for me".

Escolha **"Yup, I have an app"**.

Preencha o formulário que aparece:

| Campo | O que colocar |
|-------|---------------|
| **Repository** | `SEU_USUARIO/ccis-dashboard` (digite, ele sugere) |
| **Branch** | `main` |
| **Main file path** | `src/dashboard/app.py` |
| **App URL (opcional)** | `ccis-dashboard` (vai virar `ccis-dashboard.streamlit.app`) |

> Se `ccis-dashboard` já estiver ocupado, o Streamlit avisa — tente
> `ccis-monitor`, `ccis-anvisa`, etc.

Clique no botão azul **"Deploy"** embaixo do formulário.

### 4.3 — Aguardar o build

Uma tela preta vai aparecer mostrando logs (é o Streamlit instalando as
dependências e iniciando o app). **Leva ~2 minutos na primeira vez.**

Quando terminar, o dashboard carrega. Você vai ver a mesma interface que
está rodando localmente.

### 4.4 — Anote a URL

No topo da página do Streamlit Cloud aparece sua URL pública, algo como:

```
https://ccis-dashboard.streamlit.app
```

**Essa é a URL que você envia aos colaboradores.**

---

## PARTE 5 — Compartilhar com colaboradores

### Opção A: URL pública (qualquer um com o link vê)

Simplesmente envie o link por e-mail/WhatsApp. Sem login necessário.

⚠️ O dashboard vai ficar visível a quem tiver o link. Os dados são
anonimizados, então não há risco LGPD — mas pense se é mesmo o que você
quer.

### Opção B: Restrito a colaboradores específicos

1. Na página do app no Streamlit Cloud, clique em **"Settings"** (⚙️ no
   canto superior direito)
2. Aba **"Sharing"**
3. Em **"Who can view this app?"** → escolha **"Only specific people"**
4. Adicione os e-mails (um por linha) — cada colaborador precisa fazer
   login com Google/GitHub pra abrir

---

## PARTE 6 — Atualizar o dashboard depois

Sempre que os dados forem reprocessados (ou você mexer no código):

```bash
python scripts/prepare_deploy.py          # se reprocessou dados
git add .
git commit -m "update: descrição curta do que mudou"
git push
```

**Pronto.** O Streamlit Cloud detecta o push e redeploya automaticamente
em ~30 segundos. A URL continua a mesma.

---

## 🆘 Problemas comuns

### "gh: command not found" ou "git: command not found"
→ Feche o terminal e abra de novo. Se persistir, reinstale Git ou GitHub CLI.

### `.env` aparece no `git status`
→ **NÃO faça commit.** Rode:
```bash
git rm --cached .env
git commit -m "chore: remove .env"
```
Depois confirme que está no `.gitignore` (já deve estar).

### "Repository ccis-dashboard already exists"
→ Já existe um repo com esse nome na sua conta. Use outro:
```bash
gh repo create ccis-meu-dashboard --private --source=. --remote=origin --push
```

### No Streamlit Cloud: "ModuleNotFoundError: No module named 'src'"
→ O arquivo `src/__init__.py` não existe ou não foi commitado. Rode:
```bash
ls src/__init__.py
git add src/__init__.py
git commit -m "fix: add src __init__"
git push
```

### No Streamlit Cloud: "Nenhum dado classificado encontrado"
→ O JSON de deploy não subiu. Rode localmente:
```bash
python scripts/prepare_deploy.py
git add data/classified/classificados_deploy.json
git commit -m "data: add deploy json"
git push
```

### App ficou lento / "Zzz"
→ Streamlit Cloud grátis hiberna após 7 dias sem acesso. O primeiro acesso
depois disso leva ~30s para acordar. Normal.

### Quero apagar tudo e começar de novo
```bash
gh repo delete SEU_USUARIO/ccis-dashboard --yes
```
Depois refaça da Parte 3 em diante.

---

## 🔑 Resumo ultra-curto (para referência futura)

```bash
# Primeira vez
gh auth login                                                   # 1x só
python scripts/prepare_deploy.py
git init && git add . && git commit -m "deploy" && git branch -M main
gh repo create ccis-dashboard --private --source=. --remote=origin --push
# → depois: share.streamlit.io → New app → apontar para src/dashboard/app.py

# Atualizações
python scripts/prepare_deploy.py
git add . && git commit -m "update" && git push
```
