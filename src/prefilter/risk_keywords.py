"""Constantes de pré-filtro para classificação determinística de reclamações cosméticas.

Permite pular a API da Claude para grupos comerciais óbvios e aplicar
filtragem por keywords de risco antes de qualquer chamada de rede.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Grupos do Consumidor.gov.br classificados deterministicamente como Comercial
# (sem necessidade de chamar a API Claude)
# ---------------------------------------------------------------------------
GRUPOS_COMERCIAL_DETERMINISTICO: frozenset[str] = frozenset({
    "Cobrança / Contestação",
    "Entrega do Produto",
    "Contrato / Oferta",
    "Atendimento / SAC",
    "Dados Pessoais e Privacidade",
})

# ---------------------------------------------------------------------------
# Grupos que definitivamente precisam de classificação via Claude
# (relacionados à substância/produto cosmético em si)
# ---------------------------------------------------------------------------
GRUPOS_PRECISA_API: frozenset[str] = frozenset({
    "Vício de Qualidade",
    "Saúde e Segurança",
    "Informação",
})

# ---------------------------------------------------------------------------
# Keywords de risco cosmético
# Se NENHUMA aparecer no texto da reclamação → classificar como Comercial
# sem chamar a API. Se ao menos uma aparecer → enviar para Claude.
# ---------------------------------------------------------------------------
RISK_KEYWORDS: frozenset[str] = frozenset({
    # ── Segurança: reações adversas ────────────────────────────────────────
    "reação", "reacao", "alérgica", "alergica", "alergia",
    "irritação", "irritacao", "irritou", "irritar",
    "vermelhidão", "vermelhidao", "vermelho", "vermelhão",
    "coceira", "cocei", "coçando", "cocando",
    "descamação", "descamacao", "descamou",
    "queimadura", "queimou", "queimando", "ardeu", "ardência", "ardencia",
    "edema", "inchaço", "inchaco", "inchando", "inchei", "inchação",
    "queda de cabelo", "cabelo caindo", "calvície", "calvo",
    "intoxicação", "intoxicacao", "intoxicou",
    "bolha", "vesícula", "vesicula",
    "urticária", "urticaria",
    "dermatite", "eczema",
    "mancha", "manchas", "manchou",
    "ardor", "ardência", "ardencia",
    "inflamação", "inflamacao", "inflamou",
    "alergi", "reagi",  # prefixos (substring match)
    # ── Qualidade: defeitos físicos do produto ─────────────────────────────
    "partícula", "particula", "estranho", "impureza",
    "mofo", "mofado", "bolor", "fungo",
    "vencido", "venceu", "validade", "prazo vencido",
    "cheiro alterado", "odor estranho", "cheiro ruim", "rançoso", "rancoso",
    "cor alterada", "cor mudou", "desbotou",
    "separação", "separacao", "separou", "fase separada",
    "vazando", "vazamento", "vazou",
    "embalagem violada", "embalagem aberta", "lacre",
    "textura diferente", "textura estranha", "consistência",
    "rótulo", "rotulo", "sem rótulo",
    # ── Eficácia: produto não cumpre finalidade ────────────────────────────
    "sem efeito", "não funcionou", "nao funcionou",
    "não funciona", "nao funciona",
    "propaganda enganosa", "publicidade enganosa",
    "não hidrata", "nao hidrata",
    "não protege", "nao protege",
    "não colore", "nao colore",
    "não alisa", "nao alisa",
    "não cumpre", "nao cumpre",
    "resultado prometido", "resultado diferente",
    "falsificado", "falso", "adulterado",
})
