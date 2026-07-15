import re
import unicodedata


def clean_extracted_text(text: str) -> str:
    """
    Nettoie et normalise le texte extrait d'un fichier PDF.
    """

    if not text:
        return ""

    cleaned_text = unicodedata.normalize("NFKC", text)

    cleaned_text = cleaned_text.replace("\u00a0", " ")
    cleaned_text = cleaned_text.replace("\r\n", "\n")
    cleaned_text = cleaned_text.replace("\r", "\n")

    # Corriger directement certaines erreurs fréquentes.
    cleaned_text = cleaned_text.replace("1'énergie", "l'énergie")
    cleaned_text = cleaned_text.replace("1es", "les")
    cleaned_text = cleaned_text.replace("lls", "Ils")
    cleaned_text = cleaned_text.replace("Lesaliments", "Les aliments")
    cleaned_text = cleaned_text.replace("lesaliments", "les aliments")
    cleaned_text = cleaned_text.replace("richesen", "riches en")

    # Réunir les mots coupés par un tiret en fin de ligne.
    cleaned_text = re.sub(
        r"(\w)-\n(\w)",
        r"\1\2",
        cleaned_text,
    )

    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
    cleaned_text = re.sub(r" *\n *", "\n", cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return cleaned_text.strip()