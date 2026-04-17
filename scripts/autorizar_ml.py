"""Autorização OAuth2 do Mercado Livre — execução única.

O token de app (client_credentials) não tem acesso à busca de produtos.
Este script faz a autorização de USUÁRIO (authorization_code), que tem
acesso completo. Só precisa rodar uma vez — salva os tokens no .env.

Passo a passo:
  1. python scripts/autorizar_ml.py --step 1   → gera URL, abre no browser
  2. Autorize no site do ML
  3. Copie o CODE da URL de redirecionamento
  4. python scripts/autorizar_ml.py --step 2 --code SEU_CODE_AQUI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import httpx

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config.settings import get_settings

REDIRECT_URI = "https://ccis-dashboard.streamlit.app"


def step1_gerar_url() -> None:
    s = get_settings()
    params = {
        "response_type": "code",
        "client_id":     s.ml_client_id,
        "redirect_uri":  REDIRECT_URI,
        "scope":         "read_catalog offline_access",
    }
    url = "https://auth.mercadolivre.com.br/authorization?" + urlencode(params)

    print()
    print("=" * 65)
    print("PASSO 1 — Abra esta URL no navegador e autorize o app:")
    print("=" * 65)
    print()
    print(url)
    print()
    print("Depois de autorizar, o ML vai redirecionar para:")
    print(f"  {REDIRECT_URI}?code=XXXXXXXXXX")
    print()
    print("Copie o valor de 'code' na URL e rode:")
    print("  python scripts/autorizar_ml.py --step 2 --code SEU_CODE")
    print("=" * 65)


def step2_trocar_code(code: str) -> None:
    s = get_settings()
    print(f"\nTrocando code por token…")

    resp = httpx.post(
        "https://api.mercadolibre.com/oauth/token",
        data={
            "grant_type":    "authorization_code",
            "client_id":     s.ml_client_id,
            "client_secret": s.ml_client_secret,
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
        },
    )

    if resp.status_code != 200:
        print(f"Erro {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    access_token  = data["access_token"]
    refresh_token = data.get("refresh_token", "")
    expires_in    = data.get("expires_in", 21600)

    print(f"[OK] Access token obtido  (expira em {expires_in//3600:.0f}h)")
    print(f"[OK] Refresh token obtido (valido por ~6 meses)")

    # Salvar no .env
    env_path = _ROOT / ".env"
    env_text = env_path.read_text(encoding="utf-8")

    def upsert(text: str, key: str, value: str) -> str:
        """Atualiza ou adiciona uma chave no .env."""
        lines = text.splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}")
        return "\n".join(new_lines) + "\n"

    env_text = upsert(env_text, "ML_ACCESS_TOKEN",  access_token)
    env_text = upsert(env_text, "ML_REFRESH_TOKEN", refresh_token)
    env_path.write_text(env_text, encoding="utf-8")

    print(f"\n[OK] Tokens salvos em {env_path}")
    print("\nAgora rode a coleta:")
    print("  python scripts/coletar_ml.py --limite 100")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, choices=[1, 2], required=True)
    parser.add_argument("--code", type=str, default="")
    args = parser.parse_args()

    if args.step == 1:
        step1_gerar_url()
    elif args.step == 2:
        if not args.code:
            print("Erro: --code é obrigatório no step 2")
            sys.exit(1)
        step2_trocar_code(args.code)
