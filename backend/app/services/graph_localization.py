"""
Make the knowledge graph follow the UI language (繁體中文 / 简体中文 / English).

Two separate problems:

1. Graph *content* — entity names, entity summaries, relation facts — is written
   by Graphiti's own prompts, which are all in English and never say which
   language to answer in, so the LLM mostly answers in English. We append a
   language directive to the system message of every request Graphiti makes
   (apply_language_directive), which covers extraction, deduplication and
   summaries alike, instead of patching graphiti-core's prompts.

2. Type *names* — entity types (PascalCase) and relation types (UPPER_SNAKE) —
   must stay English identifiers: Graphiti turns them into Pydantic models and
   FalkorDB labels, and the simulation stage keys off them. They get a separate
   localized display name: the ontology generator asks for `display_name`, and
   anything still missing after a build (older ontologies, relation types
   Graphiti invented beyond the ontology) is translated once and stored on the
   project (translate_type_names / build_type_labels).
"""

import json
from typing import Any, Dict, Iterable, List, Optional

from graphiti_core.prompts.models import Message

from ..utils.locale import _languages
from ..utils.logger import get_logger

logger = get_logger('futuresreport.graph_localization')

_LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese as used in Taiwan (繁體中文)",
    "zh": "Simplified Chinese (简体中文)",
    "en": "English",
}

# Graph labels for the two built-in generic types, used when nothing better exists.
_GENERIC_LABELS = {
    "zh-TW": {"Entity": "實體", "Person": "人物", "Organization": "組織"},
    "zh": {"Entity": "实体", "Person": "人物", "Organization": "组织"},
    "en": {"Entity": "Entity", "Person": "Person", "Organization": "Organization"},
}


def language_name(locale: str) -> str:
    if locale in _LANGUAGE_NAMES:
        return _LANGUAGE_NAMES[locale]
    return (_languages.get(locale) or {}).get("label") or "Simplified Chinese (简体中文)"


def graph_language_directive(locale: str) -> str:
    """System-prompt addendum that makes Graphiti write graph content in `locale`."""
    lang = language_name(locale)
    return (
        "LANGUAGE REQUIREMENT (overrides any language implied by the examples above): "
        f"write every piece of natural-language content you produce in {lang}, regardless of "
        "the language of the source text. This covers entity names, entity summaries, "
        "relationship facts, attribute values and any descriptions. For people and "
        f"organizations, use their established name in {lang} if one exists (a well-known "
        "acronym may follow in parentheses); if none exists, keep the original name rather "
        "than inventing a transliteration. Do NOT translate JSON field names, entity type "
        "labels, relation type identifiers written in UPPER_SNAKE_CASE, or any IDs and enum "
        "values. Whenever the input already gives you entity names (for example a list of "
        "extracted entities), reuse those names exactly as written."
    )


def apply_language_directive(llm_client: Any, directive: str) -> Any:
    """Wrap `llm_client.generate_response` so every request carries `directive`
    appended to its system message. Works for any graphiti-core LLMClient
    (GeminiClient overrides generate_response, so we patch the instance)."""
    original = llm_client.generate_response

    async def generate_response(messages, *args, **kwargs):
        patched = list(messages)
        for i, message in enumerate(patched):
            if message.role == "system":
                patched[i] = Message(role="system", content=f"{message.content}\n\n{directive}")
                break
        else:
            patched.insert(0, Message(role="system", content=directive))
        return await original(patched, *args, **kwargs)

    llm_client.generate_response = generate_response
    return llm_client


# ---------------------------------------------------------------------------
# Type display names
# ---------------------------------------------------------------------------

def ontology_display_names(ontology: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """{"entity": {Name: display}, "edge": {NAME: display}} from ontology display_name fields."""
    labels = {"entity": {}, "edge": {}}
    for key, kind in (("entity_types", "entity"), ("edge_types", "edge")):
        for item in (ontology or {}).get(key) or []:
            name, display = item.get("name"), (item.get("display_name") or "").strip()
            if name and display:
                labels[kind][name] = display
    return labels


def build_type_labels(
    ontology: Optional[Dict[str, Any]],
    stored: Optional[Dict[str, Dict[str, str]]],
    locale: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """Merge generic labels < stored translations < ontology display names."""
    generic = _GENERIC_LABELS.get(locale or "", {})
    labels = {"entity": dict(generic), "edge": {}}
    for source in (stored or {}, ontology_display_names(ontology)):
        for kind in ("entity", "edge"):
            labels[kind].update((source or {}).get(kind) or {})
    return labels


def missing_type_names(
    ontology: Optional[Dict[str, Any]],
    stored: Optional[Dict[str, Dict[str, str]]],
    entity_names: Iterable[str],
    edge_names: Iterable[str],
    locale: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Type names that still have no display name (ontology types + whatever the graph uses)."""
    known = build_type_labels(ontology, stored, locale)
    entities = {e.get("name") for e in (ontology or {}).get("entity_types") or []} | set(entity_names)
    edges = {e.get("name") for e in (ontology or {}).get("edge_types") or []} | set(edge_names)
    return {
        "entity": sorted(n for n in entities if n and n != "Entity" and n not in known["entity"]),
        "edge": sorted(n for n in edges if n and n not in known["edge"]),
    }


def translate_type_names(llm_client: Any, missing: Dict[str, List[str]], locale: str) -> Dict[str, Dict[str, str]]:
    """One LLM call that returns display names for the given identifiers.
    Never raises: a failed translation just leaves the identifiers as they are."""
    if locale == "en" or not (missing.get("entity") or missing.get("edge")):
        return {"entity": {}, "edge": {}}

    lang = language_name(locale)
    messages = [
        {
            "role": "system",
            "content": (
                f"You translate knowledge-graph type identifiers into short, natural {lang} labels "
                "for a user interface. Entity types are PascalCase nouns (e.g. ClimateScientist); "
                "relation types are UPPER_SNAKE_CASE verb phrases (e.g. WORKS_FOR). Keep each label "
                "concise (2-8 characters for Chinese). Return JSON only: "
                '{"entity": {"<identifier>": "<label>"}, "edge": {"<identifier>": "<label>"}} '
                "with exactly the identifiers you were given as keys."
            ),
        },
        {"role": "user", "content": json.dumps(missing, ensure_ascii=False)},
    ]
    try:
        result = llm_client.chat_json(messages=messages, temperature=0.2, max_tokens=4096)
    except Exception as exc:
        logger.warning(f"type-name translation failed (labels stay as identifiers): {exc}")
        return {"entity": {}, "edge": {}}

    out = {"entity": {}, "edge": {}}
    for kind in ("entity", "edge"):
        wanted = set(missing.get(kind) or [])
        for name, label in ((result or {}).get(kind) or {}).items():
            if name in wanted and isinstance(label, str) and label.strip():
                out[kind][name] = label.strip()
    return out
