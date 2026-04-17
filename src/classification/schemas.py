"""Schemas Pydantic para classificação de reclamações cosméticas."""

from typing import Literal

from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Resultado da classificação de uma reclamação."""

    categoria: Literal["Segurança", "Qualidade", "Eficácia", "Comercial"]
    severidade: int = Field(ge=1, le=5, description="Escala 1-5 de gravidade")
    confianca: float = Field(ge=0.0, le=1.0, description="Confiança na classificação")
    justificativa: str = Field(description="Explicação breve da classificação")
    palavras_chave: list[str] = Field(description="Termos-chave extraídos do texto")


class ComplaintRecord(BaseModel):
    """Registro de reclamação para entrada no classificador."""

    id: str
    texto_anonimizado: str
    fonte: str
    data_reclamacao: str | None = None
    empresa: str | None = None
    segmento: str | None = None
    assunto: str | None = None


class ClassifiedComplaint(BaseModel):
    """Reclamação com resultado de classificação associado."""

    record: ComplaintRecord
    classification: ClassificationResult | None = None
    error: str | None = None
