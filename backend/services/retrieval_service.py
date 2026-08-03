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

RETRIEVAL_SERVICE_VERSION = "v18-arabic-muslim-qualities-full-coverage"


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

    if question_is_arabic:
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

    initial_results = search_similar_chunks(
        question=search_question,
        number_of_results=candidate_count,
        program=program,
        subject=subject,
        semester=semester,
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