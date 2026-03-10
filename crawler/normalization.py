"""Normalization utilities for Open Library crawler payloads.

This module transforms raw Open Library records into deterministic, taxonomy-
aligned dictionaries that can be persisted by downstream pipelines.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, TypedDict

from crawler.taxonomy_config import (
    AgeBandEntry,
    SpiceLevelEntry,
    TaxonomyEntry,
    get_age_bands,
    get_all_character_dynamics,
    get_all_genres,
    get_all_plot_tags,
    get_spice_levels,
    get_taxonomy_version,
)

TOKEN_PATTERN = re.compile(r"[a-z0-9']+")
WHITESPACE_PATTERN = re.compile(r"\s+")


class NormalizedOpenLibraryBook(TypedDict):
    """Canonical normalized Open Library payload shape."""

    source: str
    taxonomy_version: str
    title: str
    authors: list[str]
    description: str | None
    canonical_genres: list[str]
    canonical_plot_tags: list[str]
    canonical_character_dynamics: list[str]
    genres: list[str]
    plot_tags: list[str]
    character_dynamics: list[str]
    age_band: str
    spice_level: str


GENRE_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "fantasy": ("fantasy", "magic", "sword", "dragon", "fae", "wizard"),
    "science-fiction": (
        "science fiction",
        "sci fi",
        "space",
        "robot",
        "cyberpunk",
        "dystopia",
    ),
    "mystery": (
        "mystery",
        "detective",
        "investigation",
        "whodunit",
        "murder mystery",
    ),
    "thriller": ("thriller", "suspense", "psychological"),
    "romance": (
        "romance",
        "love story",
        "romantic",
        "boyfriend",
        "girlfriend",
    ),
    "historical-fiction": (
        "historical fiction",
        "historical",
        "victorian",
        "world war",
    ),
    "horror": ("horror", "ghost", "haunted", "supernatural terror"),
    "young-adult": ("young adult", "ya", "teen", "high school"),
    "children": (
        "children",
        "juvenile",
        "kids",
        "middle grade",
        "bedtime",
    ),
    "literary-fiction": ("literary", "character study", "booker"),
    "contemporary-fiction": (
        "contemporary",
        "modern life",
        "domestic fiction",
    ),
    "adventure": ("adventure", "quest", "expedition", "journey"),
    "dystopian": ("dystopia", "post apocalyptic", "apocalypse", "totalitarian"),
    "paranormal": (
        "paranormal",
        "vampire",
        "werewolf",
        "shifter",
        "witch",
    ),
    "graphic-novel": ("graphic novel", "comic", "manga"),
    "non-fiction": ("nonfiction", "memoir", "biography", "history", "essay"),
}

PLOT_TAG_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "coming-of-age": ("coming of age", "growing up", "adolescence"),
    "found-family": ("found family", "chosen family"),
    "revenge": ("revenge", "vengeance"),
    "survival": ("survival", "survive", "stranded"),
    "redemption": ("redemption", "atonement"),
    "heist": ("heist", "caper", "robbery"),
    "quest": ("quest", "journey", "mission"),
    "political-intrigue": ("political intrigue", "court politics", "conspiracy"),
    "war": ("war", "battle", "military"),
    "murder-investigation": (
        "murder investigation",
        "detective case",
        "investigation",
    ),
    "forbidden-love": ("forbidden love", "star crossed"),
    "second-chance": ("second chance", "fresh start"),
    "slow-burn-romance": ("slow burn", "slow-burn"),
    "time-travel": ("time travel", "time-travel"),
    "identity-secrets": ("secret identity", "hidden identity", "secret past"),
    "competition": ("competition", "tournament", "contest"),
}

CHARACTER_DYNAMIC_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "enemies-to-lovers": ("enemies to lovers", "adversaries to lovers"),
    "friends-to-lovers": ("friends to lovers", "best friends"),
    "mentor-mentee": ("mentor", "teacher student", "teacher-student"),
    "rivals": ("rivals", "rivalry"),
    "siblings": ("siblings", "brothers and sisters"),
    "parent-child": ("parent child", "mother daughter", "father son"),
    "partners-in-crime": ("partners in crime", "criminal duo"),
    "reluctant-allies": ("reluctant allies", "forced alliance"),
    "team-ensemble": ("ensemble cast", "group cast", "team"),
    "love-triangle": ("love triangle", "romantic triangle"),
    "grumpy-sunshine": ("grumpy sunshine", "opposites attract"),
    "bodyguard-ward": ("bodyguard", "protector"),
    "detective-suspect": ("detective and suspect", "cat and mouse"),
}

AGE_BAND_KEYWORD_WEIGHTS: dict[str, dict[str, int]] = {
    "middle-grade": {
        "children": 3,
        "juvenile": 3,
        "middle grade": 3,
        "kids": 2,
        "ages 8-12": 3,
        "grade school": 2,
    },
    "young-adult": {
        "young adult": 3,
        "ya": 3,
        "teen": 3,
        "teenager": 3,
        "high school": 2,
        "coming of age": 1,
    },
    "new-adult": {
        "new adult": 3,
        "college": 2,
        "university": 2,
        "early twenties": 2,
    },
    "adult": {
        "adult": 2,
        "erotica": 3,
        "explicit": 3,
        "dark romance": 2,
        "violence": 1,
    },
}

SPICE_LEVEL_KEYWORD_WEIGHTS: dict[int, dict[str, int]] = {
    1: {
        "clean": 3,
        "sweet romance": 2,
        "children": 3,
        "juvenile": 3,
        "middle grade": 3,
        "no romance": 2,
    },
    2: {
        "closed door": 3,
        "fade to black": 3,
        "kissing": 1,
        "mild romance": 2,
    },
    3: {
        "young adult": 2,
        "new adult": 1,
        "sensual": 2,
        "steamy": 2,
        "spicy": 1,
    },
    4: {
        "open door": 3,
        "explicit scenes": 3,
        "high heat": 3,
        "dark romance": 2,
        "erotic romance": 2,
    },
    5: {
        "erotica": 4,
        "very explicit": 4,
        "graphic sex": 4,
        "extreme heat": 3,
    },
}


def normalize_openlibrary_book(raw_book: dict[str, Any]) -> NormalizedOpenLibraryBook:
    """Normalize an Open Library payload to canonical taxonomy identifiers."""
    title = _normalize_text(raw_book.get("title")) or "Untitled"
    description = _extract_description(raw_book.get("description"))
    authors = _extract_authors(raw_book.get("authors"))

    text_corpus = _build_text_corpus(raw_book=raw_book, description=description)
    canonical_genres = _infer_taxonomy_ids(
        text_corpus=text_corpus,
        taxonomy_entries=get_all_genres(),
        keyword_map=GENRE_KEYWORD_MAP,
        include_open_library_hints=True,
    )
    canonical_plot_tags = _infer_taxonomy_ids(
        text_corpus=text_corpus,
        taxonomy_entries=get_all_plot_tags(),
        keyword_map=PLOT_TAG_KEYWORD_MAP,
    )
    canonical_character_dynamics = _infer_taxonomy_ids(
        text_corpus=text_corpus,
        taxonomy_entries=get_all_character_dynamics(),
        keyword_map=CHARACTER_DYNAMIC_KEYWORD_MAP,
    )

    age_band = _infer_age_band(text_corpus)
    spice_level = _infer_spice_level(text_corpus, age_band=age_band)

    return {
        "source": "openlibrary",
        "taxonomy_version": get_taxonomy_version(),
        "title": title,
        "authors": authors,
        "description": description,
        "canonical_genres": canonical_genres,
        "canonical_plot_tags": canonical_plot_tags,
        "canonical_character_dynamics": canonical_character_dynamics,
        # aliases retained for downstream convenience.
        "genres": canonical_genres,
        "plot_tags": canonical_plot_tags,
        "character_dynamics": canonical_character_dynamics,
        "age_band": age_band,
        "spice_level": spice_level,
    }


def _extract_authors(raw_authors: Any) -> list[str]:
    if not isinstance(raw_authors, list):
        return []

    authors: list[str] = []
    for entry in raw_authors:
        author_name = ""
        if isinstance(entry, str):
            author_name = _normalize_text(entry)
        elif isinstance(entry, dict):
            author_name = _normalize_text(
                entry.get("name")
                or (entry.get("author") or {}).get("name")
                or (entry.get("author") or {}).get("key")
            )
        if author_name:
            authors.append(author_name)

    return _dedupe_preserve_order(authors)


def _extract_description(raw_description: Any) -> str | None:
    if isinstance(raw_description, str):
        return _normalize_text(raw_description) or None
    if isinstance(raw_description, dict):
        return _normalize_text(raw_description.get("value")) or None
    return None


def _build_text_corpus(raw_book: dict[str, Any], description: str | None) -> str:
    values: list[str] = []

    for field_name in (
        "title",
        "subtitle",
        "first_sentence",
        "by_statement",
    ):
        value = _normalize_text(raw_book.get(field_name))
        if value:
            values.append(value)

    if description:
        values.append(description)

    for list_field in (
        "subjects",
        "subject_people",
        "subject_places",
        "subject_times",
    ):
        field_values = raw_book.get(list_field)
        if isinstance(field_values, list):
            values.extend(_normalize_text(item) for item in field_values)

    excerpts = raw_book.get("excerpts")
    if isinstance(excerpts, list):
        for excerpt in excerpts:
            if isinstance(excerpt, dict):
                values.append(_normalize_text(excerpt.get("excerpt")))

    return " ".join(value for value in values if value).lower()


def _infer_taxonomy_ids(
    text_corpus: str,
    taxonomy_entries: tuple[TaxonomyEntry, ...],
    keyword_map: dict[str, tuple[str, ...]],
    include_open_library_hints: bool = False,
) -> list[str]:
    allowed_ids = {entry.identifier for entry in taxonomy_entries}
    matched: list[str] = []

    for entry in taxonomy_entries:
        if entry.identifier not in allowed_ids:
            continue

        keyword_set = set(keyword_map.get(entry.identifier, ()))
        keyword_set.add(entry.label.lower())
        keyword_set.update(s.lower() for s in entry.synonyms)
        if include_open_library_hints:
            keyword_set.update(h.lower() for h in entry.open_library_subject_hints)

        if _contains_any_phrase(text_corpus, keyword_set):
            matched.append(entry.identifier)

    return matched


def _infer_age_band(text_corpus: str) -> str:
    scores = _score_identifier_matches(text_corpus, AGE_BAND_KEYWORD_WEIGHTS)

    best_identifier = _best_identifier(scores)
    if best_identifier is not None:
        return best_identifier

    young_adult_hits = _count_keywords(text_corpus, {"teen", "young adult", "ya"})
    if young_adult_hits:
        return "young-adult"

    return "adult"


def _infer_spice_level(text_corpus: str, age_band: str) -> str:
    scores = _score_rank_matches(text_corpus, SPICE_LEVEL_KEYWORD_WEIGHTS)

    if age_band == "middle-grade":
        scores[1] += 4
    elif age_band == "young-adult":
        scores[2] += 1
        scores[3] += 2
    elif age_band == "new-adult":
        scores[3] += 2
        scores[4] += 1

    if not any(scores.values()):
        return _spice_identifier_for_rank(2)

    best_rank = _best_rank(scores)
    return _spice_identifier_for_rank(best_rank)


def _spice_identifier_for_rank(level: int) -> str:
    spice_by_level = {entry.level: entry.identifier for entry in get_spice_levels()}
    return spice_by_level.get(level, "spice-2-mild")


def _score_identifier_matches(
    text_corpus: str,
    weighted_keywords: dict[str, dict[str, int]],
) -> dict[str, int]:
    scores: dict[str, int] = defaultdict(int)
    for identifier, keyword_weights in weighted_keywords.items():
        for phrase, weight in keyword_weights.items():
            scores[identifier] += _count_phrase_occurrences(text_corpus, phrase) * weight

    valid_ids = {entry.identifier for entry in get_age_bands()}
    return {identifier: score for identifier, score in scores.items() if identifier in valid_ids}


def _score_rank_matches(
    text_corpus: str,
    weighted_keywords: dict[int, dict[str, int]],
) -> dict[int, int]:
    scores: dict[int, int] = defaultdict(int)
    for rank, keyword_weights in weighted_keywords.items():
        for phrase, weight in keyword_weights.items():
            scores[rank] += _count_phrase_occurrences(text_corpus, phrase) * weight

    valid_ranks = {entry.level for entry in get_spice_levels()}
    return {rank: score for rank, score in scores.items() if rank in valid_ranks}


def _best_identifier(scores: dict[str, int]) -> str | None:
    if not scores:
        return None

    top_score = max(scores.values())
    if top_score <= 0:
        return None

    rank_order = {entry.identifier: index for index, entry in enumerate(get_age_bands())}
    candidates = [identifier for identifier, score in scores.items() if score == top_score]
    candidates.sort(key=lambda item: rank_order.get(item, 999))
    return candidates[0] if candidates else None


def _best_rank(scores: dict[int, int]) -> int:
    top_score = max(scores.values())
    candidates = [rank for rank, score in scores.items() if score == top_score]
    return max(candidates)


def _contains_any_phrase(text_corpus: str, phrases: set[str]) -> bool:
    return any(_count_phrase_occurrences(text_corpus, phrase) > 0 for phrase in phrases)


def _count_keywords(text_corpus: str, keywords: set[str]) -> int:
    return sum(_count_phrase_occurrences(text_corpus, keyword) for keyword in keywords)


def _count_phrase_occurrences(text_corpus: str, phrase: str) -> int:
    normalized_phrase = _normalize_text(phrase).lower()
    if not normalized_phrase:
        return 0

    phrase_tokens = _tokenize(normalized_phrase)
    corpus_tokens = _tokenize(text_corpus)
    if not phrase_tokens or not corpus_tokens:
        return 0

    phrase_length = len(phrase_tokens)
    hits = 0
    for idx in range(0, len(corpus_tokens) - phrase_length + 1):
        if corpus_tokens[idx : idx + phrase_length] == phrase_tokens:
            hits += 1
    return hits


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return WHITESPACE_PATTERN.sub(" ", value).strip()


def _tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


__all__ = ["NormalizedOpenLibraryBook", "normalize_openlibrary_book"]
