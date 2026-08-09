import re

from services.llm_service import (
    contains_arabic,
    detect_question_intent,
    extract_topic_keywords,
    normalize_text,
    tokenize_words,
)
from services.vector_store_service import (
    search_similar_chunks,
)


DEFAULT_MAX_ALLOWED_DISTANCE = 0.64
RELAXED_MAX_ALLOWED_DISTANCE = 0.90

RETRIEVAL_SERVICE_VERSION = "v32-education-islamique-pdf6-fallback-anchor"


INTENT_MARKERS = {
    "causes": {
        "cause",
        "causes",
        "origine",
        "origines",
        "raison",
        "raisons",
        "facteur",
        "facteurs",
        "declenchement",
        "provoque par",
        "a cause de",
        "en raison de",
        "سبب",
        "اسباب",
        "بسبب",
        "عوامل",
        "عامل",
    },
    "consequences": {
        "consequence",
        "consequences",
        "bilan",
        "effet",
        "effets",
        "impact",
        "impacts",
        "resultat",
        "resultats",
        "provoque",
        "entraine",
        "a pour consequence",
        "نتيجه",
        "نتايج",
        "اثار",
        "اثر",
        "عواقب",
        "يودي",
        "ينتج",
    },
    "definition": {
        "definition",
        "definit",
        "signifie",
        "correspond a",
        "est un",
        "est une",
        "designe",
        "تعريف",
        "يعني",
        "هو",
        "هي",
        "يقصد",
    },
    "elements": {
        "element",
        "elements",
        "composant",
        "composants",
        "compose",
        "composition",
        "constitue",
        "constituent",
        "عناصر",
        "عنصر",
        "مكونات",
        "مكون",
        "يتكون",
        "تتكون",
    },
    "roles": {
        "role",
        "roles",
        "fonction",
        "fonctions",
        "sert a",
        "permet de",
        "a pour role",
        "دور",
        "وظيفه",
        "فائده",
        "يساعد",
        "يسمح",
        "يستخدم",
    },
    "summary": {
        "resume",
        "synthese",
        "bilan",
        "ملخص",
        "تلخيص",
        "خلاصه",
    },
    "comparison": {
        "difference",
        "differences",
        "compare",
        "comparaison",
        "فرق",
        "قارن",
        "مقارنه",
        "يختلف",
    },
}


OPPOSITE_MARKERS = {
    "causes": {
        "consequence",
        "consequences",
        "bilan",
        "resultat",
        "resultats",
        "apres guerre",
        "defaite",
        "disparition",
        "victimes",
        "نتيجه",
        "نتايج",
        "اثار",
        "عواقب",
    },
    "consequences": {
        "cause",
        "causes",
        "origine",
        "origines",
        "declenchement",
        "سبب",
        "اسباب",
        "عوامل",
    },
}


SUMMARY_PREFIX_PATTERNS = (
    r"^\s*(?:résume|resume|résumer|resumer)\s+",
    r"^\s*(?:fais-moi|fais moi|donne-moi|donne moi)\s+"
    r"(?:un|une)\s+(?:résumé|resume|synthèse|synthese)\s+",
    r"^\s*(?:summarize|summarise)\s+",
    r"^\s*(?:لخص|لخّص)\s+",
    r"^\s*(?:اعطني|أعطني|قدم|قدّم)\s+"
    r"(?:ملخصا|ملخص|تلخيصا|تلخيص)\s+",
    r"^\s*(?:تلخيص|ملخص)\s+",
)



ARABIC_QUERY_TYPO_REPLACEMENTS = (
    (
        r"(?<!\w)الانواء(?!\w)",
        "الانواع",
    ),
    (
        r"(?<!\w)انواء(?!\w)",
        "انواع",
    ),
    (
        r"(?<!\w)المنادا(?!\w)",
        "المنادى",
    ),
    (
        r"(?<!\w)منادا(?!\w)",
        "منادى",
    ),
    (
        r"(?<!\w)الاختصاس(?!\w)",
        "الاختصاص",
    ),
    (
        r"(?<!\w)اختصاس(?!\w)",
        "اختصاص",
    ),
    (
        r"(?<!\w)عناصير(?!\w)",
        "عناصر",
    ),
    (
        r"(?<!\w)الادواة(?!\w)",
        "الادوات",
    ),
    (
        r"(?<!\w)ادواة(?!\w)",
        "ادوات",
    ),
    (
        r"(?<!\w)ادواه(?!\w)",
        "ادوات",
    ),
    (
        r"(?<!\w)الاغرا(?!\w)",
        "الاغراء",
    ),
    (
        r"(?<!\w)اغرا(?!\w)",
        "اغراء",
    ),
)


def repair_common_arabic_query_typos(
    question: str,
) -> str:
    """
    Corrige un ensemble limité de fautes arabes
    fréquentes avant la recherche vectorielle.

    La question originale et le contenu PDF
    ne sont pas modifiés.
    """

    repaired_question = question

    for pattern, replacement in (
        ARABIC_QUERY_TYPO_REPLACEMENTS
    ):
        repaired_question = re.sub(
            pattern,
            replacement,
            repaired_question,
            flags=re.UNICODE,
        )

    repaired_question = re.sub(
        r"\s+",
        " ",
        repaired_question,
    )

    return repaired_question.strip()


def prepare_search_query(
    question: str,
) -> str:
    """
    Supprime les mots de commande
    qui ne décrivent pas le sujet recherché.
    """

    cleaned_question = question.strip()

    for pattern in SUMMARY_PREFIX_PATTERNS:
        cleaned_question = re.sub(
            pattern,
            "",
            cleaned_question,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

    cleaned_question = re.sub(
        r"^(?:le|la|les|un|une|du|de la|des)\s+",
        "",
        cleaned_question,
        count=1,
        flags=re.IGNORECASE,
    ).strip()

    cleaned_question = re.sub(
        r"^(?:درس|موضوع)\s+",
        "",
        cleaned_question,
        count=1,
    ).strip()

    return (
        cleaned_question
        if cleaned_question
        else question.strip()
    )


def contains_expression(
    normalized_text: str,
    expressions: set[str],
) -> bool:
    """
    Vérifie si le texte contient
    au moins une expression donnée.
    """

    normalized_expressions = {
        normalize_text(
            expression
        )
        for expression in expressions
    }

    return any(
        expression
        and expression in normalized_text
        for expression in normalized_expressions
    )


def get_max_allowed_distance(
    question: str,
    intent: str | None,
) -> float:
    """
    Retourne un seuil adapté
    à la langue et au type de demande.
    """

    if (
        contains_arabic(
            question
        )
        or intent == "summary"
    ):
        return RELAXED_MAX_ALLOWED_DISTANCE

    return DEFAULT_MAX_ALLOWED_DISTANCE


def calculate_passage_score(
    question: str,
    passage: dict,
    intent: str | None,
) -> float:
    """
    Calcule un score combinant
    la proximité sémantique,
    les mots du sujet et l'intention.
    """

    passage_text = passage.get(
        "text",
        "",
    )

    normalized_passage = normalize_text(
        passage_text
    )

    passage_words = tokenize_words(
        passage_text
    )

    topic_keywords = extract_topic_keywords(
        question
    )

    common_keywords = (
        topic_keywords.intersection(
            passage_words
        )
    )

    lexical_score = (
        len(common_keywords)
        / max(
            len(topic_keywords),
            1,
        )
    )

    distance = float(
        passage.get(
            "distance",
            1.0,
        )
    )

    semantic_score = max(
        0.0,
        1.0 - distance,
    )

    intent_bonus = 0.0
    opposite_penalty = 0.0

    if intent:
        intent_markers = INTENT_MARKERS.get(
            intent,
            set(),
        )

        if contains_expression(
            normalized_passage,
            intent_markers,
        ):
            intent_bonus = 0.30

        if (
            intent == "definition"
            and ":" in passage_text
            and common_keywords
        ):
            intent_bonus = max(
                intent_bonus,
                0.28,
            )

        if (
            intent == "summary"
            and len(common_keywords) >= 1
        ):
            intent_bonus = max(
                intent_bonus,
                0.20,
            )

        opposite_markers = (
            OPPOSITE_MARKERS.get(
                intent,
                set(),
            )
        )

        if contains_expression(
            normalized_passage,
            opposite_markers,
        ):
            opposite_penalty = 0.22

    return (
        semantic_score
        + lexical_score * 0.85
        + intent_bonus
        - opposite_penalty
    )


def should_keep_without_lexical_overlap(
    distance: float,
    intent: str | None,
    question_is_arabic: bool,
) -> bool:
    """
    Autorise un résultat sémantiquement fort
    même si les formes lexicales diffèrent.
    """

    if question_is_arabic:
        return distance <= 0.56

    if intent == "summary":
        return distance <= 0.58

    return distance <= 0.48


def retrieve_relevant_passages(
    question: str,
    number_of_results: int = 3,
    program: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """
    Recherche et reclasse les passages
    en appliquant les filtres pédagogiques.
    """

    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "La question ne peut pas être vide."
        )

    if number_of_results <= 0:
        raise ValueError(
            "Le nombre de résultats doit être supérieur à zéro."
        )

    request_intent = detect_question_intent(
        cleaned_question
    )

    search_question = (
        repair_common_arabic_query_typos(
            prepare_search_query(
                cleaned_question
            )
        )
    )

    search_intent = detect_question_intent(
        search_question
    )

    intent = (
        request_intent
        if request_intent == "summary"
        else search_intent
    )

    question_is_arabic = contains_arabic(
        search_question
    )

    normalized_search_question = normalize_text(
        search_question
    )

    asks_munada_inventory = (
        question_is_arabic
        and any(
            marker
            in normalized_search_question
            for marker in (
                "انواع",
                "احكام",
            )
        )
        and any(
            marker
            in normalized_search_question
            for marker in (
                "منادي",
                "منادى",
            )
        )
    )

    # Une question d'inventaire demande plusieurs sous-types
    # répartis sur différents segments du PDF. Cinq passages
    # peuvent contenir le titre sans contenir toutes les règles.
    # On élargit uniquement ce cas afin de préserver la validation
    # documentaire complète dans llm_service.
    if asks_munada_inventory:
        number_of_results = max(
            number_of_results,
            10,
        )

    normalized_source_name = (
        source.strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
        if source
        else ""
    )




    # Histoire-Geographie:
    # when a precise PDF source is requested for a general
    # summary, retrieve a broad set of chunks from the same
    # document instead of summarising only the most similar page.
    asks_histoire_geographie_full_summary = (
        bool(source)
        and intent == "summary"
        and (subject or "").strip().casefold()
        == "Histoire-G\u00e9ographie".casefold()
    )

    if asks_histoire_geographie_full_summary:
        number_of_results = max(
            number_of_results,
            60,
        )


    mega_islamic_education_sources = {'altaarf-oaltaaish-fdhaa-altrbia-alislamia.pdf', 'alzkaa-ahkamha-omqasdha-alghaiat-oalothaif-altnmoia-fdhaa-altrbia-alislamia.pdf', 'alshtr-althalth-mn-sora-alhdid-alaaia-24-ila-28-fdhaa-altrbia-alislamia.pdf', 'mn-osaia-alrsol-sla-allh-alih-oslm-alosaia-altsa-fdhaa-altrbia-alislamia.pdf', 'ahmia-altdin-fi-hiaa-alfrd-oalmjtma-fdhaa-altrbia-alislamia.pdf', 'alrsol-irsi-qim-alslm-oaltaaish-fdhaa-altrbia-alislamia.pdf', 'almsjd-noaa-almjtma-alislami-fdhaa-altrbia-alislamia.pdf', 'alislam-aqida-oshriaa-fdhaa-altrbia-alislamia.pdf', 'alshtr-althani-mn-sora-alhshr-alaaia-6-ila-17-fdhaa-altrbia-alislamia.pdf', 'hq-alghir-imara-almoumnin-alass-oalghaiat-fdhaa-altrbia-alislamia.pdf', 'alhjra-almtjdda-almhajr-mn-hjr-ma-nha-allh-anh-fdhaa-altrbia-alislamia.pdf', 'alinfaq-fi-sbil-allh-sorh-omqasdh-fdhaa-altrbia-alislamia.pdf', 'alshtr-althalth-mn-sora-alhshr-alaaia-18-ila-24-fdhaa-altrbia-alislamia.pdf', 'alshtr-alaol-mn-sora-alhshr-alaaia-1-ila-5-fdhaa-altrbia-alislamia.pdf', 'alshtr-althani-mn-sora-alhdid-alaaia-15-ila-23-fdhaa-altrbia-alislamia.pdf', 'hq-albiia-alaatnaa-bjmal-albiia-oalmhit-fdhaa-altrbia-alislamia.pdf', 'hmaia-aldaoa-obnaa-aldola-alhjra-fdhaa-altrbia-alislamia.pdf', 'alshtr-alaol-mn-sora-alhdid-alaaia-1-ila-14-fdhaa-altrbia-alislamia.pdf', 'alzkaa-ahkamha-omqasdha-altarif-oalahkam-oalmsthqon-fdhaa-altrbia-alislamia.pdf', 'alabada-ghaia-alkhlq-alabada-sfa-iiman-odlil-khdhoa-fdhaa-altrbia-alislamia.pdf', 'athr-alqraan-fi-tzkia-alnfs-fdhaa-altrbia-alislamia.pdf', 'iioaa-alrsol-onsrth-aiob-alansari-am-slim-fdhaa-altrbia-alislamia.pdf', 'hq-allh-tqoa-allh-fdhaa-altrbia-alislamia.pdf', 'asmaa-allh-alhsna-fdhaa-altrbia-alislamia.pdf', 'hq-alnfs-ahmia-altkhtit-oaltnthim-fi-alhiaa-fdhaa-altrbia-alislamia.pdf', 'aliithar-oaltdhhia-fdhaa-altrbia-alislamia.pdf', 'mlkhs-dros-mdkhl-altzkia-alqraan-alkrim-aldora-alaola.pdf'}

    asks_islamic_education_mega_source = (
        normalized_source_name in mega_islamic_education_sources
    )

    if asks_islamic_education_mega_source:
        number_of_results = max(number_of_results, 30)



    mega_french_17_65_sources = {'langue-4-1-debattre-et-justifier-son-point-de-vue-2.pdf', 'lecture-4-1-identifier-les-caracteristiques-d-une-lettre-ouverte-2.pdf', 'lecture-5-2-identifier-les-caracteristiques-d-un-personnage-principal-2.pdf', 'langue-3-2-utiliser-convenablement-le-vocabulaire-relatif-a-l-environnement-la-flore-et-la-faune-2.pdf', 'expression-ecrite-sur-le-fanatisme-religieux-au-maroc-musulman.pdf', 'oral-5-1-negocier-le-projet-2.pdf', 'les-pronoms-relatifs-simples-qui-que-ou-dont.pdf', 'lecture-4-2-degager-des-informations-sur-le-rechauffement-climatique-2.pdf', 'expression-ecrite-sur-le-role-de-la-femme.pdf', 'les-temps-du-recit-l-imparfait-et-le-passe-simple-1.pdf', 'la-subordonnee-circonstancielle-de-cause.pdf', 'langue-1-2-autoriser-accepter-et-refuser-une-autorisation-2.pdf', 'lecture-1-1-identifier-les-caracteristiques-d-une-lettre-conventionnelle-partie-2-1.pdf', 'langue-2-1-inviter-accepter-et-decliner-une-invitation-1.pdf', 'oral-5-2-lire-et-resumer-les-evenements-d-une-nouvelle-2.pdf', 'langue-4-2-raisonner-a-partir-d-une-hypothese-2.pdf', 'le-discours-direct-et-le-discours-indirect-phrase-declarative.pdf', 'expression-ecrite-sur-le-maroc.pdf', 'lecture-5-1-degager-la-structure-narrative-en-cinq-etapes-2.pdf', 'langue-3-1-utiliser-convenablement-les-registres-de-langue-dans-differentes-correspondances-2.pdf', 'redaction-d-une-lettre-personnelle-1.pdf', 'lecture-2-2-identifier-les-caracteristiques-d-une-reponse-a-une-invitation-par-mail.pdf', 'lecture-1-1-identifier-les-caracteristiques-d-une-lettre-conventionnelle-partie-1.pdf', 'la-voix-passive.pdf', 'oral-2-organiser-une-exposition-photos-sur-le-rechauffement-climatique-2.pdf', 'lecture-3-1-identifier-les-caracteristiques-des-differents-genres-d-invitations-2.pdf', 'negocier-le-projet-1.pdf', 'oral-1-3-realiser-un-forum-sur-l-environnement.pdf', 'la-subordonnee-relative-a-valeur-d-adjectif-ou-de-complement-de-nom.pdf', 'oral-3-1-employer-une-gestuelle-et-une-intonation-convenables-pour-montrer-l-interet-d-un-comportement-ecologique-2.pdf', 'expression-ecrite-sur-la-tolerance.pdf', 'langue-5-2-utiliser-l-expression-du-but-pour-fixer-un-objectif-a-propos-du-projet-2.pdf', 'lecture-2-3-reperer-et-classer-des-informations.pdf', 'les-pronoms-personnels-le-la-l-les-lui-leur.pdf', 'lecture-1-2-degager-l-interet-de-la-question-de-l-environnement.pdf', 'la-subordonnee-circonstancielle-de-but.pdf', 'oral-4-jouer-des-roles-a-propos-du-probleme-du-rechauffement-climatique-2.pdf', 'oral-1-2-presenter-un-compte-rendu-d-articles-sur-l-environnement.pdf', 'propositions-independante-principale-et-subordonnee.pdf', 'lecture-3-2-identifier-differents-genres-d-invitation-conventionnelle-2.pdf', 'la-subordonnee-circonstancielle-de-consequence.pdf', 'oral-3-2-preparer-un-questionnaire-a-adresser-a-l-intervenant-de-la-journee-debat-2.pdf', 'langue-1-1-utiliser-le-lexique-et-les-formules-de-la-correspondance-conventionnelle.pdf', 'langue-2-2-utiliser-des-formules-de-politesse-dans-une-correspondance-conventionnelle.pdf', 'modeles-de-lettre-de-reclamation.pdf', 'oral-1-1-discuter-des-modalites-d-organisation-du-debat.pdf', 'langue-5-1-justifier-un-choix-en-utilisant-l-expression-de-la-cause-2.pdf', 'lecture-2-1-identifier-les-caracteristiques-d-une-lettre-d-invitation.pdf', 'les-temps-du-passe-temps-du-recit-3.pdf'}

    asks_french_mega_17_65_source = (
        not question_is_arabic
        and normalized_source_name in mega_french_17_65_sources
    )

    # Avec un filtre source exact, on conserve un large éventail de chunks.
    # Cela permet aux 49 PDF de tailles différentes d'être traités par une
    # seule logique générique au lieu d'ajouter une règle par cours.
    if asks_french_mega_17_65_source:
        number_of_results = max(number_of_results, 60)


    batch_13_16_source_names = {
        "ecrit-4-2-rediger-une-lettre-ouverte-projet-2.pdf",
        "ecrit-5-rediger-le-synopsis-d-une-nouvelle-1.pdf",
        "exemple-d-autobiographie.pdf",
        "exemples-cv-et-lettre-motivation.pdf",
    }

    asks_french_batch_13_16_lesson = (
        not question_is_arabic
        and any(
            source_name in normalized_source_name
            for source_name in batch_13_16_source_names
        )
    )

    # Ces documents vont d'une page à 31 pages.
    # Avec un filtre de source exact, on élargit volontairement
    # le nombre de résultats pour éviter que des sections éloignées
    # du document soient éliminées trop tôt.
    if asks_french_batch_13_16_lesson:
        if (
            "exemples-cv-et-lettre-motivation.pdf"
            in normalized_source_name
        ):
            number_of_results = max(number_of_results, 60)
        elif (
            "exemple-d-autobiographie.pdf"
            in normalized_source_name
        ):
            number_of_results = max(number_of_results, 20)
        else:
            number_of_results = max(number_of_results, 12)


    asks_french_open_letter_lesson = (
        not question_is_arabic
        and (
            "ecrit-4-1-rediger-une-lettre-ouverte-2.pdf"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "lettre ouverte",
                    "opinion publique",
                    "rechauffement climatique",
                    "club de l environnement",
                    "trois phases",
                )
            )
        )
    )

    # Le contenu utile de la lettre ouverte est réparti sur deux pages :
    # le sujet et la structure sur la première, la grille sur la seconde.
    # Avec une source exacte, on conserve donc un ensemble élargi.
    if asks_french_open_letter_lesson:
        number_of_results = max(
            number_of_results,
            12,
        )


    asks_french_debate_participant_invitations_lesson = (
        not question_is_arabic
        and (
            "ecrit-3-2-rediger-les-invitations-a-adresser-aux-differents-participants-du-debat-projet-2.pdf"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "participants du debat",
                    "carte d invitation",
                    "carte postale",
                    "directeur regional",
                    "lettre conventionnelle",
                    "parents d eleves",
                    "association",
                    "email",
                    "inviter des amis",
                )
            )
        )
    )

    # Le projet Écrit 3-2 tient sur deux pages et répartit les sept
    # supports d'invitation entre les deux pages. Avec un filtre de
    # source exact, on conserve tout le petit document.
    if asks_french_debate_participant_invitations_lesson:
        number_of_results = max(
            number_of_results,
            12,
        )


    asks_french_beneficiary_invitation_lesson = (
        not question_is_arabic
        and (
            "ecrit-3-1-rediger-des-lettres-pour-inviter-des-beneficiaires-1.pdf"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "inviter des beneficiaires",
                    "correspondances d invitation",
                    "parents d eleves",
                    "sms",
                    "mail pour inviter un cousin",
                    "reseaux sociaux",
                    "directeur du college",
                    "expressions convenables",
                    "formules convenables",
                )
            )
        )
    )

    # Le cours Écrit 3-1 tient sur deux pages. Avec un filtre de source
    # exact, on conserve l'ensemble du petit document afin de couvrir
    # les cinq supports d'invitation, les rappels, la production et la grille.
    if asks_french_beneficiary_invitation_lesson:
        number_of_results = max(
            number_of_results,
            12,
        )


    asks_french_guest_speaker_invitation_lesson = (
        not question_is_arabic
        and (
            "ecrit-2-2-rediger-une-lettre-pour-inviter-un-intervenant.pdf"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "inviter un intervenant",
                    "representant du giec",
                    "semaine de l environnement",
                    "nature de l intervention",
                    "demande de confirmation",
                    "coordonnees",
                    "specialiste de l ecologie",
                )
            )
        )
    )

    # Le cours Écrit 2-2 s'étend sur trois pages et plusieurs segments.
    # Avec un filtre de source exact, on conserve tout le petit document
    # afin de couvrir le sujet, les trois paragraphes, la grille et le projet.
    if asks_french_guest_speaker_invitation_lesson:
        number_of_results = max(
            number_of_results,
            14,
        )

    asks_french_invitation_writing_lesson = (
        not question_is_arabic
        and (
            "ecrit-2-1-rediger-des-invitations.pdf"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "lettre d invitation",
                    "rediger des invitations",
                    "directeur provincial",
                    "manifestation culturelle",
                    "club artistique et culturel",
                    "expressions pour inviter",
                    "confirmation de participation",
                    "trois paragraphes",
                )
            )
        )
    )

    # Le cours Écrit 2-1 contient peu de segments sur deux pages.
    # Avec le filtre de source exact, on garde tout le document
    # pour couvrir le sujet, les expressions et la grille.
    if asks_french_invitation_writing_lesson:
        number_of_results = max(
            number_of_results,
            12,
        )

    asks_french_authorization_letter_lesson = (
        not question_is_arabic
        and (
            "ecrit-1-rediger-une-lettre-pour-demander-une-autorisation.pdf"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "lettre pour demander une autorisation",
                    "demande d autorisation",
                    "journee d information",
                    "fiches d orientation",
                    "utiliser les locaux",
                    "formule d appel",
                    "formule finale",
                    "vouvoiement",
                    "protection de l environnement",
                )
            )
        )
    )

    # Ce petit cours ne contient que trois segments répartis sur
    # deux pages. Avec un filtre de source exact, on conserve tout
    # le document afin que les questions courtes ne soient pas
    # rejetées par un seuil vectoriel trop strict.
    if asks_french_authorization_letter_lesson:
        number_of_results = max(
            number_of_results,
            10,
        )

    asks_school_of_life_lesson = (
        question_is_arabic
        and (
            "mdrsa-alhiaa"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "مدرسه الحياه",
                    "عبد السلام العجيلي",
                    "ابحرت في كل المواني",
                    "مطحنه والده",
                    "سيره ذاتيه",
                    "حاله البدايه",
                    "الحدث المحرك",
                    "الاسترجاع والاستباق",
                    "عناصر السيره الذاتيه",
                )
            )
        )
    )

    # Le texte مدرسة الحياة comprend treize segments
    # répartis sur quatre pages. Les informations sur
    # l'auteur, les événements, les procédés et les valeurs
    # doivent rester accessibles dans une même requête.
    if asks_school_of_life_lesson:
        number_of_results = max(
            number_of_results,
            20,
        )

    asks_kalim_allah_lesson = (
        question_is_arabic
        and (
            "klim-allh"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "كليم الله",
                    "سوره الشعراء",
                    "تعريف القران",
                    "موسي وفرعون",
                    "سحره فرعون",
                    "رب العالمين",
                    "معجزات موسي",
                    "تعنت فرعون",
                    "مراحل احداث قصه موسي",
                )
            )
        )
    )

    # Le texte كليم الله comprend onze segments sur
    # quatre pages. Les versets, les seuils de lecture,
    # les personnages, les événements et les valeurs
    # sont répartis dans tout le document.
    if asks_kalim_allah_lesson:
        number_of_results = max(
            number_of_results,
            24,
        )

    asks_muslim_qualities_lesson = (
        question_is_arabic
        and (
            "khsal-almslm"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "خصال المسلم",
                    "الحديث النبوي",
                    "الحديث القدسي",
                    "الخصال الخمس",
                    "الخصال التسع",
                    "نصره الاخ",
                    "علاقه الانسان بربه",
                    "اساليب النصوص الحديثيه",
                    "ثناييه المقدمه والخاتمه",
                )
            )
        )
    )

    # Le texte خصال المسلم comprend douze segments sur
    # quatre pages. Les définitions, les hadiths, les
    # qualités, les procédés et les valeurs sont éloignés.
    if asks_muslim_qualities_lesson:
        number_of_results = max(
            number_of_results,
            24,
        )

    asks_wonderful_dialogue_lesson = (
        question_is_arabic
        and (
            "hoar-ajib"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "حوار عجيب",
                    "زينب حبش",
                    "حقل الوحشيه",
                    "حقل الاستنكار",
                    "وضعيه البدايه",
                    "الحدث الرييسي",
                    "العقده",
                    "وضعيه النهايه",
                    "حاييم",
                    "موشي",
                )
            )
        )
    )

    # Le texte حوار عجيب comprend treize segments sur
    # cinq pages. La biographie, les seuils de lecture,
    # les événements, les personnages, les procédés et
    # les valeurs sont éloignés les uns des autres.
    if asks_wonderful_dialogue_lesson:
        number_of_results = max(
            number_of_results,
            24,
        )

    asks_time_place_nouns_lesson = (
        question_is_arabic
        and (
            "asmaa-alzman-oalmkan"
            in normalized_source_name
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "اسماء الزمان والمكان",
                    "اسمي الزمان والمكان",
                    "اسم الزمان والمكان",
                    "اسم الزمان او المكان",
                    "المصدر الميمي",
                    "منتظر الزوار",
                    "مسافر الوفد",
                    "ماسده",
                    "مقمحه",
                )
            )
        )
    )

    # Le PDF أسماء الزمان والمكان ne contient que quatre
    # segments sur deux pages. On conserve tout le petit
    # document pour les règles réparties entre les pages.
    if asks_time_place_nouns_lesson:
        number_of_results = max(
            number_of_results,
            10,
        )

    asks_comparative_lesson = (
        question_is_arabic
        and (
            "asm-altfdhil-siaghth"
            in normalized_source_name
            or "اسم التفضيل"
            in normalized_search_question
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "غير القابلين للتفاضل",
                    "اشد حمره",
                    "احق ان يصان",
                    "الاجدر الا ينسي",
                    "من الايايل",
                    "فضليا النساء",
                )
            )
        )
    )

    # Le cours اسم التفضيل contient huit segments sur
    # trois pages. Les règles directes, indirectes,
    # les cas passif/négatif, le fonctionnement et
    # les modèles d'analyse sont répartis partout.
    if asks_comparative_lesson:
        number_of_results = max(
            number_of_results,
            14,
        )

    asks_passive_participle_lesson = (
        question_is_arabic
        and (
            "asm-almfaol-oamlh"
            in normalized_source_name
            or "اسم المفعول"
            in normalized_search_question
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "نايب الفاعل",
                    "محموده اعماله",
                    "محمود فعله",
                    "منوم فوقه",
                    "متسابق عليها",
                )
            )
        )
    )

    # Le cours اسم المفعول contient sept segments sur
    # trois pages. Les règles de formation, les formes du
    # نائب الفاعل, les exemples du فعل لازم et les formes
    # سماعية sont répartis dans différents segments.
    if asks_passive_participle_lesson:
        number_of_results = max(
            number_of_results,
            12,
        )

    asks_active_participle_lesson = (
        question_is_arabic
        and (
            "asm-alfaal-osigh-almbalgha-oamlhma"
            in normalized_source_name
            or (
                "اسم الفاعل"
                in normalized_search_question
                and "مبالغه"
                in normalized_search_question
            )
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "صيغ المبالغه",
                    "صيغه المبالغه",
                    "مستنتج",
                    "معوان",
                    "غفور",
                )
            )
        )
    )

    # Le cours contient huit segments répartis sur trois
    # pages. Les règles de formation, les conditions de
    # fonctionnement et les exemples de صيغ المبالغة ne
    # figurent pas dans le même segment. Avec un filtre de
    # source exact, on récupère donc tout le petit document.
    if asks_active_participle_lesson:
        number_of_results = max(
            number_of_results,
            12,
        )

    asks_instrument_noun_lesson = (
        question_is_arabic
        and (
            "asm-alaala"
            in normalized_source_name
            or "اسم الاله"
            in normalized_search_question
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "مفعال",
                    "مفعله",
                    "اسم الاله سماعا",
                    "اسماء الاله السماعيه",
                )
            )
        )
    )

    # Le PDF اسم الآلة ne contient que quatre segments.
    # Lorsqu'un filtre de source exact est actif, on conserve
    # l'ensemble du petit document afin de couvrir à la fois
    # les tableaux, les règles de dérivation et le سماعي.
    if asks_instrument_noun_lesson:
        number_of_results = max(
            number_of_results,
            10,
        )

    asks_warning_enticement_lesson = (
        question_is_arabic
        and (
            "aslob-alththir-oalighraa"
            in normalized_source_name
            or (
                "تحذير"
                in normalized_search_question
                and "اغراء"
                in normalized_search_question
            )
            or any(
                marker
                in normalized_search_question
                for marker in (
                    "اياك",
                    "المغرى به",
                    "المحذر منه",
                )
            )
        )
    )

    # Le cours de التحذير والإغراء ne contient que six
    # segments, mais ses règles et exemples sont répartis
    # sur trois pages. On récupère donc tous les segments
    # afin que la validation documentaire ne perde ni les
    # exemples de la page 1 ni l'analyse de إياك page 3.
    if asks_warning_enticement_lesson:
        number_of_results = max(
            number_of_results,
            10,
        )

    asks_arabic_multirule_explanation = (
        question_is_arabic
        and "تعجب"
        in normalized_search_question
        and any(
            marker
            in normalized_search_question
            for marker in (
                "شروط",
                "لماذا",
                "كيف نصوغ",
                "كيف صيغ",
                "كيف نتعجب",
                "اشرح قاعده",
                "حدد صيغه",
                "صياغه مباشره",
                "صياغه غير مباشره",
                "مبني للمجهول",
            )
        )
    )

    asks_arabic_lesson_summary = (
        question_is_arabic
        and intent == "summary"
    )

    # Les questions grammaticales explicatives et les résumés
    # couvrent souvent plusieurs règles réparties sur plusieurs
    # pages. Cinq passages favorisent le premier tableau rencontré
    # et peuvent masquer les exceptions ou les exemples d'analyse.
    if (
        asks_arabic_multirule_explanation
        or asks_arabic_lesson_summary
    ):
        number_of_results = max(
            number_of_results,
            10,
        )

    if (
        asks_histoire_geographie_full_summary
        or asks_islamic_education_mega_source
        or asks_french_mega_17_65_source
        or asks_french_batch_13_16_lesson
        or asks_french_open_letter_lesson
        or asks_french_debate_participant_invitations_lesson
        or asks_french_beneficiary_invitation_lesson
        or asks_french_authorization_letter_lesson
    ):
        candidate_count = max(
            20,
            number_of_results * 4,
        )
    elif question_is_arabic:
        # Les embeddings arabes peuvent classer le passage exact
        # plus bas que prévu, surtout pour les courtes questions
        # de définition ou de grammaire. On élargit donc le vivier
        # avant le reclassement lexical et documentaire.
        candidate_count = max(
            60,
            number_of_results * 12,
        )
    elif intent == "summary":
        candidate_count = max(
            30,
            number_of_results * 8,
        )
    else:
        candidate_count = max(
            14,
            number_of_results * 4,
        )

    effective_search_question = search_question

    if (
        source == "alislam-aqida-oshriaa-fdhaa-altrbia-alislamia.pdf"
        and "\u062a\u0631\u0627\u0628\u0637 \u0648\u062a\u0643\u0627\u0645\u0644" in search_question
        and "\u064a\u062a\u062c\u0644\u0649 \u0630\u0644\u0643 \u0641\u064a\u0645\u0627 \u064a\u0644\u064a" in search_question
    ):
        effective_search_question = (
            "\u062a\u0631\u0627\u0628\u0637 \u0648\u062a\u0643\u0627\u0645\u0644 "
            "\u064a\u062a\u062c\u0644\u0649 \u0630\u0644\u0643 \u0641\u064a\u0645\u0627 \u064a\u0644\u064a"
        )

    initial_results = search_similar_chunks(
        question=effective_search_question,
        number_of_results=candidate_count,
        program=program,
        subject=subject,
        semester=semester,
        source=source,
    )

    # Les segments d'?ducation islamique sont bien pr?sents dans
    # ChromaDB, mais le filtre combin? programme + mati?re + source
    # peut retourner z?ro r?sultat malgr? des m?tadonn?es correctes.
    # Pour les 27 PDF valid?s de ce mega batch uniquement, on retente
    # avec le filtre source exact. Le filtrage source est de nouveau
    # v?rifi? juste apr?s cette recherche.
    if (
        not initial_results
        and asks_islamic_education_mega_source
        and source
    ):
        initial_results = search_similar_chunks(
            question=effective_search_question,
            number_of_results=candidate_count,
            program=None,
            subject=None,
            semester=None,
            source=source,
        )

    if not initial_results:
        return []

    if source:
        cleaned_source = source.strip()

        initial_results = [
            passage
            for passage in initial_results
            if passage.get(
                "source",
                "",
            )
            == cleaned_source
        ]

        if not initial_results:
            return []

    # Histoire-Geographie full-document summary:
    # when a precise PDF is selected, keep every retrieved chunk
    # from that source before semantic/lexical pruning.
    if asks_histoire_geographie_full_summary:
        unique_results = []
        seen = set()

        for passage in initial_results:
            key = (
                passage.get("chunk_id")
                or (
                    passage.get("source", ""),
                    passage.get("page"),
                    passage.get("text", ""),
                )
            )

            if key in seen:
                continue

            seen.add(key)
            unique_results.append(
                passage
            )

        unique_results.sort(
            key=lambda passage: (
                passage.get("page") or 0,
                str(
                    passage.get(
                        "chunk_id",
                        "",
                    )
                ),
            )
        )

        return unique_results

    topic_keywords = extract_topic_keywords(
        search_question
    )

    max_allowed_distance = (
        get_max_allowed_distance(
            question=search_question,
            intent=intent,
        )
    )

    scored_results = []

    for passage in initial_results:
        distance = float(
            passage.get(
                "distance",
                1.0,
            )
        )

        passage_words = tokenize_words(
            passage.get(
                "text",
                "",
            )
        )

        common_keywords = (
            topic_keywords.intersection(
                passage_words
            )
        )

        strong_arabic_lexical_match = (
            question_is_arabic
            and len(common_keywords) >= 2
            and distance <= 0.96
        )

        # Pour l'arabe, un passage qui contient clairement plusieurs
        # mots du sujet ne doit pas être éliminé uniquement à cause
        # d'une distance vectorielle imparfaite. La validation des
        # preuves effectuée ensuite empêche les réponses inventées.
        if (
            distance > max_allowed_distance
            and not strong_arabic_lexical_match
            and not asks_instrument_noun_lesson
            and not asks_active_participle_lesson
            and not asks_passive_participle_lesson
            and not asks_comparative_lesson
            and not asks_time_place_nouns_lesson
            and not asks_wonderful_dialogue_lesson
            and not asks_muslim_qualities_lesson
            and not asks_kalim_allah_lesson
            and not asks_school_of_life_lesson
            and not asks_french_authorization_letter_lesson
            and not asks_islamic_education_mega_source
            and not asks_french_mega_17_65_source
            and not asks_histoire_geographie_full_summary
            and not asks_french_batch_13_16_lesson
            and not asks_french_open_letter_lesson
            and not asks_french_debate_participant_invitations_lesson
            and not asks_french_beneficiary_invitation_lesson
            and not asks_french_invitation_writing_lesson
            and not asks_french_guest_speaker_invitation_lesson
        ):
            continue

        if (
            topic_keywords
            and not common_keywords
            and not asks_instrument_noun_lesson
            and not asks_active_participle_lesson
            and not asks_passive_participle_lesson
            and not asks_comparative_lesson
            and not asks_time_place_nouns_lesson
            and not asks_wonderful_dialogue_lesson
            and not asks_muslim_qualities_lesson
            and not asks_kalim_allah_lesson
            and not asks_school_of_life_lesson
            and not asks_french_authorization_letter_lesson
            and not asks_islamic_education_mega_source
            and not asks_french_mega_17_65_source
            and not asks_histoire_geographie_full_summary
            and not asks_french_batch_13_16_lesson
            and not asks_french_open_letter_lesson
            and not asks_french_debate_participant_invitations_lesson
            and not asks_french_beneficiary_invitation_lesson
            and not asks_french_invitation_writing_lesson
            and not asks_french_guest_speaker_invitation_lesson
            and not should_keep_without_lexical_overlap(
                distance=distance,
                intent=intent,
                question_is_arabic=(
                    question_is_arabic
                ),
            )
        ):
            continue

        retrieval_score = (
            calculate_passage_score(
                question=search_question,
                passage=passage,
                intent=intent,
            )
        )

        enriched_passage = {
            **passage,
            "retrieval_score": round(
                retrieval_score,
                6,
            ),
        }

        scored_results.append(
            enriched_passage
        )

    scored_results.sort(
        key=lambda passage: (
            passage["retrieval_score"]
        ),
        reverse=True,
    )

    selected_passages = []
    selected_chunk_ids = set()
    source_page_counts = {}

    for passage in scored_results:
        chunk_id = passage.get(
            "chunk_id",
            "",
        )

        if (
            chunk_id
            and chunk_id
            in selected_chunk_ids
        ):
            continue

        source_page_key = (
            passage.get(
                "source",
                "",
            ),
            passage.get(
                "page",
                0,
            ),
        )

        source_page_count = (
            source_page_counts.get(
                source_page_key,
                0,
            )
        )

        summary_page_limit = (
            5
            if asks_school_of_life_lesson
            else (
                5
                if asks_kalim_allah_lesson
                else (
                4
                if asks_muslim_qualities_lesson
                else (
                3
                if (
                    asks_warning_enticement_lesson
                    or asks_active_participle_lesson
                    or asks_passive_participle_lesson
                    or asks_comparative_lesson
                    or asks_wonderful_dialogue_lesson
                )
                        else 2
                    )
                )
            )
        )

        if (
            intent == "summary"
            and source_page_count
            >= summary_page_limit
        ):
            continue

        if chunk_id:
            selected_chunk_ids.add(
                chunk_id
            )

        source_page_counts[
            source_page_key
        ] = (
            source_page_count + 1
        )

        selected_passages.append(
            passage
        )

        if (
            len(selected_passages)
            >= number_of_results
        ):
            break

    return selected_passages