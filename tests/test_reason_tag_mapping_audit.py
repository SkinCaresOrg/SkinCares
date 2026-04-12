import importlib
import re
from pathlib import Path


app_module = importlib.import_module("deployment.api.app")


def _load_frontend_reason_tags() -> set[str]:
    frontend_types_path = (
        Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "types.ts"
    )
    raw = frontend_types_path.read_text(encoding="utf-8")

    reaction_block_match = re.search(
        r"export\s+const\s+REACTION_TAGS(?:\s*:\s*[^=]+)?\s*=\s*\{(?P<body>.*?)\};",
        raw,
        flags=re.DOTALL,
    )
    irritation_match = re.search(
        r"export\s+const\s+IRRITATION_TAGS(?:\s*:\s*[^=]+)?\s*=\s*\[(?P<body>.*?)\];",
        raw,
        flags=re.DOTALL,
    )

    assert reaction_block_match is not None, (
        "Could not find REACTION_TAGS in frontend types.ts"
    )
    assert irritation_match is not None, (
        "Could not find IRRITATION_TAGS in frontend types.ts"
    )

    quoted_strings_pattern = r'"([a-z0-9_]+)"'
    reaction_tags = set(
        re.findall(quoted_strings_pattern, reaction_block_match.group("body"))
    )
    irritation_tags = set(
        re.findall(quoted_strings_pattern, irritation_match.group("body"))
    )

    all_tags = reaction_tags | irritation_tags
    assert all_tags, "No reason tags parsed from frontend types.ts"
    return all_tags


# Source of truth: frontend tag vocabulary parsed from Swiping tag definitions.
FRONTEND_REASON_TAGS = _load_frontend_reason_tags()


# Must be explicitly decided and implemented in structured signal extraction.
STRUCTURED_REASON_TAGS = {
    "price_too_high",
    "good_value",
    "non_irritating",
}


# Explicitly allowed to flow only through generic reason-token adjustment for now.
GENERIC_ONLY_REASON_TAGS = FRONTEND_REASON_TAGS - STRUCTURED_REASON_TAGS


def _normalize(tag: str) -> str:
    return tag.lower().replace("_", " ").strip()


def test_every_frontend_tag_is_explicitly_classified() -> None:
    classified = STRUCTURED_REASON_TAGS | GENERIC_ONLY_REASON_TAGS
    assert FRONTEND_REASON_TAGS == classified


def test_structured_reason_tags_are_backed_by_backend_triggers() -> None:
    trigger_phrases = (
        set(app_module._PRICE_NEGATIVE_TRIGGERS)
        | set(app_module._PRICE_POSITIVE_TRIGGERS)
        | set(app_module._SKIN_TYPE_POSITIVE_TRIGGERS)
        | set(app_module._INGREDIENT_POSITIVE_TRIGGERS)
        | set(app_module._AVOID_INGREDIENT_TRIGGERS.keys())
    )
    normalized_triggers = {
        phrase.lower().replace("_", " ").strip() for phrase in trigger_phrases
    }

    missing = [
        tag
        for tag in sorted(STRUCTURED_REASON_TAGS)
        if _normalize(tag) not in normalized_triggers
    ]
    assert not missing, f"Structured tags missing backend trigger mapping: {missing}"


def test_generic_only_tags_do_not_overlap_structured_set() -> None:
    assert STRUCTURED_REASON_TAGS.isdisjoint(GENERIC_ONLY_REASON_TAGS)
