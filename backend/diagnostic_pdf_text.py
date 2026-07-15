from pathlib import Path

import fitz

from services.text_cleaner import clean_extracted_text


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "les_aliments_partie_2.pdf"
)


def afficher_contexte(texte: str, mot: str) -> None:
    position = texte.find(mot)

    if position == -1:
        print(f"Le mot « {mot} » est introuvable.")
        return

    debut = max(0, position - 30)
    fin = min(len(texte), position + len(mot) + 30)
    contexte = texte[debut:fin]

    print(f"\nContexte autour de « {mot} » :")
    print(f"Représentation : {repr(contexte)}")
    print(
        "Codes Unicode :",
        [f"U+{ord(caractere):04X}" for caractere in contexte],
    )


with fitz.open(PDF_PATH) as document:
    texte_brut = document[0].get_text("text")

texte_nettoye = clean_extracted_text(texte_brut)

print("=== TEXTE BRUT ===")
afficher_contexte(texte_brut, "bâtiseurs")
afficher_contexte(texte_brut, "protéines")

print("\n=== TEXTE NETTOYÉ ===")
afficher_contexte(texte_nettoye, "bâtiseurs")
afficher_contexte(texte_nettoye, "protéines")