"""Baixa o modelo spaCy para português (pt_core_news_lg)."""

import spacy.cli


def main() -> None:
    print("Baixando modelo spaCy pt_core_news_lg...")
    spacy.cli.download("pt_core_news_lg")
    print("Modelo baixado com sucesso.")


if __name__ == "__main__":
    main()
