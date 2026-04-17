"""Padrões regex para detecção de PII brasileiro (LGPD)."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIPattern:
    """Padrão de PII com regex compilado e placeholder de substituição."""

    label: str
    pattern: re.Pattern[str]
    placeholder: str


# Ordem importa: padrões mais específicos primeiro para evitar matches parciais
PII_PATTERNS: list[PIIPattern] = [
    # CNPJ: XX.XXX.XXX/XXXX-XX (antes de CPF para evitar match parcial)
    PIIPattern(
        label="CNPJ",
        pattern=re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
        placeholder="[CNPJ_REMOVIDO]",
    ),
    # CPF: XXX.XXX.XXX-XX
    PIIPattern(
        label="CPF",
        pattern=re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
        placeholder="[CPF_REMOVIDO]",
    ),
    # E-mail
    PIIPattern(
        label="EMAIL",
        pattern=re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
        placeholder="[EMAIL_REMOVIDO]",
    ),
    # Telefone: (XX) XXXXX-XXXX ou (XX) XXXX-XXXX
    PIIPattern(
        label="TELEFONE",
        pattern=re.compile(
            r"\(?\b\d{2}\)?\s*\d{4,5}[\s-]?\d{4}\b"
        ),
        placeholder="[TELEFONE_REMOVIDO]",
    ),
    # CEP: XXXXX-XXX
    PIIPattern(
        label="CEP",
        pattern=re.compile(r"\b\d{5}-?\d{3}\b"),
        placeholder="[CEP_REMOVIDO]",
    ),
    # RG: padrões comuns (XX.XXX.XXX-X ou variações)
    PIIPattern(
        label="RG",
        pattern=re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}-?[\dxX]\b"),
        placeholder="[RG_REMOVIDO]",
    ),
]


def detect_pii_regex(text: str) -> list[dict[str, str | int]]:
    """Detecta todas as ocorrências de PII via regex no texto.

    Returns:
        Lista de dicts com: label, start, end, placeholder.
    """
    detections: list[dict[str, str | int]] = []
    for pii in PII_PATTERNS:
        for match in pii.pattern.finditer(text):
            detections.append({
                "label": pii.label,
                "start": match.start(),
                "end": match.end(),
                "placeholder": pii.placeholder,
            })
    return detections


def replace_pii_regex(text: str) -> tuple[str, list[dict[str, str | int]]]:
    """Substitui todas as ocorrências de PII por placeholders.

    Returns:
        Tupla (texto_anonimizado, lista_de_detecções).
    """
    detections = detect_pii_regex(text)

    # Ordena do final para o início para manter posições válidas durante substituição
    detections.sort(key=lambda d: d["start"], reverse=True)

    result = text
    for det in detections:
        start = int(det["start"])
        end = int(det["end"])
        result = result[:start] + str(det["placeholder"]) + result[end:]

    return result, detections
