"""
Named Entity Recognition pass for building knowledge graph nodes.
Falls back gracefully if spacy/nltk is unavailable.
"""
import re

_SPACY_TYPES = {"PERSON", "ORG", "LAW", "GPE", "EVENT", "WORK_OF_ART"}

# 2-4 capitalised words in a row (the generic "proper noun phrase" heuristic).
_CAP_PHRASE = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})\b")

_DOMAIN_PATTERNS = {
    "legal": [
        (r"\bSection\s+\d+\w*", "LAW"),
        (r"\bArticle\s+\d+\w*", "LAW"),
        (r"\bAct\s+of\s+\d{4}", "LAW"),
        (r"§\s*\d+\w*", "LAW"),
    ],
    "medical": [
        (r"\b[A-Z]{2,5}\b", "DRUG"),
        (r"\b[a-zA-Z]{3,}(?:mab|ine|ase|cillin|olol|pril|sartan)\b", "DRUG"),
    ],
}


def _is_sentence_initial(text: str, start: int) -> bool:
    i = start - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    return i < 0 or text[i] in ".!?\n"


def _regex_concepts(plain_text: str, domain: str):
    found = []
    seen = set()
    for m in _CAP_PHRASE.finditer(plain_text):
        if _is_sentence_initial(plain_text, m.start()):
            continue
        key = (m.group(1), m.start())
        if key in seen:
            continue
        seen.add(key)
        found.append(
            {"text": m.group(1), "label": "CONCEPT", "start": m.start(), "end": m.end()}
        )
    for pat, label in _DOMAIN_PATTERNS.get(domain, []):
        for m in re.finditer(pat, plain_text):
            found.append(
                {"text": m.group(0), "label": label, "start": m.start(), "end": m.end()}
            )
    found.sort(key=lambda c: c["start"])
    return found


def _spacy_concepts(plain_text: str):
    import spacy

    nlp = None
    for model in ("en_core_web_trf", "en_core_web_sm"):
        try:
            nlp = spacy.load(model)
            break
        except Exception:
            continue
    if nlp is None:
        return None
    doc = nlp(plain_text)
    return [
        {"text": e.text, "label": e.label_, "start": e.start_char, "end": e.end_char}
        for e in doc.ents
        if e.label_ in _SPACY_TYPES
    ]


def _nltk_concepts(plain_text: str):
    from nltk import ne_chunk, pos_tag, word_tokenize

    out = []
    tree = ne_chunk(pos_tag(word_tokenize(plain_text)))
    cursor = 0
    for node in tree:
        if hasattr(node, "label"):
            text = " ".join(tok for tok, _ in node.leaves())
            idx = plain_text.find(text, cursor)
            if idx < 0:
                idx = plain_text.find(text)
            start = idx if idx >= 0 else cursor
            out.append(
                {"text": text, "label": node.label(), "start": start, "end": start + len(text)}
            )
            if idx >= 0:
                cursor = idx + len(text)
    return out


def extract_concepts(plain_text, domain="general"):
    """Return concept spans as ``[{"text","label","start","end"}, ...]``.

    Uses spaCy when available, then NLTK, then a pure-regex heuristic that needs
    no third-party package. *domain* tunes the regex fallback for legal/medical
    text; the ML backends ignore it.
    """
    plain_text = plain_text or ""
    if not plain_text.strip():
        return []
    try:
        result = _spacy_concepts(plain_text)
        if result is not None:
            return result
    except Exception:
        pass
    try:
        return _nltk_concepts(plain_text)
    except Exception:
        pass
    return _regex_concepts(plain_text, domain)


def suggest_auto_tags(plain_text, existing_annotations, domain="general"):
    """Cross-reference extracted concepts with existing annotations.

    Returns ``[(concept_text, [matching_ann_ids]), ...]`` for concepts whose text
    appears in an existing annotation's anchor or note — candidate relation edges.
    """
    from .annotations import _ensure_id

    concepts = extract_concepts(plain_text, domain)
    anns = list(existing_annotations or [])
    out = []
    seen = set()
    for c in concepts:
        text = c["text"]
        low = text.lower()
        if low in seen:
            continue
        seen.add(low)
        matches = []
        for ann in anns:
            hay = f"{ann.get('anchor', '')} {ann.get('note', '')}".lower()
            if low in hay:
                matches.append(_ensure_id(ann))
        if matches:
            out.append((text, matches))
    return out
