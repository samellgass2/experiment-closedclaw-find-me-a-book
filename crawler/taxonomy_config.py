"""Static v1 taxonomy configuration for crawler normalization workflows.

This module intentionally keeps taxonomy definitions in immutable, in-code
structures so downstream normalization code has a single canonical source of
truth that is not user-editable at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

TAXONOMY_VERSION: Final[str] = "v1"


@dataclass(frozen=True, slots=True)
class TaxonomyEntry:
    """Canonical taxonomy item used by genre/tag dimensions."""

    identifier: str
    label: str
    synonyms: tuple[str, ...] = ()
    open_library_subject_hints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgeBandEntry:
    """Canonical age-band taxonomy item for recommendation filtering."""

    identifier: str
    label: str
    min_age: int
    max_age: int
    maturity_rating: str
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SpiceLevelEntry:
    """Canonical spice-level taxonomy item on an ordered 1-5 scale."""

    identifier: str
    label: str
    level: int
    maturity_rating_hint: str
    synonyms: tuple[str, ...] = ()


# Genres capture broad browsing categories used in UI and normalization.
_GENRES: Final[tuple[TaxonomyEntry, ...]] = (
    TaxonomyEntry(
        identifier="fantasy",
        label="Fantasy",
        synonyms=("epic fantasy", "magic"),
        open_library_subject_hints=("fantasy fiction", "magic"),
    ),
    TaxonomyEntry(
        identifier="science-fiction",
        label="Science Fiction",
        synonyms=("sci-fi", "speculative science"),
        open_library_subject_hints=("science fiction", "space opera"),
    ),
    TaxonomyEntry(
        identifier="mystery",
        label="Mystery",
        synonyms=("crime mystery", "whodunit"),
        open_library_subject_hints=("mystery fiction", "detective and mystery stories"),
    ),
    TaxonomyEntry(
        identifier="thriller",
        label="Thriller",
        synonyms=("suspense", "psychological thriller"),
        open_library_subject_hints=("thrillers", "suspense fiction"),
    ),
    TaxonomyEntry(
        identifier="romance",
        label="Romance",
        synonyms=("love story", "romantic fiction"),
        open_library_subject_hints=("love stories", "romance fiction"),
    ),
    TaxonomyEntry(
        identifier="historical-fiction",
        label="Historical Fiction",
        synonyms=("period fiction", "historical novel"),
        open_library_subject_hints=("historical fiction", "history"),
    ),
    TaxonomyEntry(
        identifier="horror",
        label="Horror",
        synonyms=("supernatural horror", "dark fiction"),
        open_library_subject_hints=("horror tales", "ghost stories"),
    ),
    TaxonomyEntry(
        identifier="young-adult",
        label="Young Adult",
        synonyms=("ya", "teen fiction"),
        open_library_subject_hints=("young adult fiction", "teenagers"),
    ),
    TaxonomyEntry(
        identifier="children",
        label="Children's",
        synonyms=("juvenile", "kids fiction"),
        open_library_subject_hints=("juvenile fiction", "children's stories"),
    ),
    TaxonomyEntry(
        identifier="literary-fiction",
        label="Literary Fiction",
        synonyms=("contemporary literary", "literary"),
        open_library_subject_hints=("fiction", "literature"),
    ),
    TaxonomyEntry(
        identifier="contemporary-fiction",
        label="Contemporary Fiction",
        synonyms=("modern fiction",),
        open_library_subject_hints=("contemporary fiction",),
    ),
    TaxonomyEntry(
        identifier="adventure",
        label="Adventure",
        synonyms=("action adventure", "quest fiction"),
        open_library_subject_hints=("adventure stories",),
    ),
    TaxonomyEntry(
        identifier="dystopian",
        label="Dystopian",
        synonyms=("post-apocalyptic", "anti-utopia"),
        open_library_subject_hints=("dystopias", "apocalyptic fiction"),
    ),
    TaxonomyEntry(
        identifier="paranormal",
        label="Paranormal",
        synonyms=("urban fantasy", "supernatural"),
        open_library_subject_hints=("paranormal fiction", "supernatural fiction"),
    ),
    TaxonomyEntry(
        identifier="graphic-novel",
        label="Graphic Novel",
        synonyms=("comics", "sequential art"),
        open_library_subject_hints=("graphic novels", "comic books, strips"),
    ),
    TaxonomyEntry(
        identifier="non-fiction",
        label="Nonfiction",
        synonyms=("narrative nonfiction", "informational"),
        open_library_subject_hints=("nonfiction", "popular works"),
    ),
)


_PLOT_TAGS: Final[tuple[TaxonomyEntry, ...]] = (
    TaxonomyEntry(
        identifier="coming-of-age",
        label="Coming of Age",
        synonyms=("bildungsroman", "growing up"),
    ),
    TaxonomyEntry(
        identifier="found-family",
        label="Found Family",
        synonyms=("chosen family",),
    ),
    TaxonomyEntry(
        identifier="revenge",
        label="Revenge",
        synonyms=("vengeance",),
    ),
    TaxonomyEntry(
        identifier="survival",
        label="Survival",
        synonyms=("against the odds",),
    ),
    TaxonomyEntry(
        identifier="redemption",
        label="Redemption",
        synonyms=("atonement",),
    ),
    TaxonomyEntry(
        identifier="heist",
        label="Heist",
        synonyms=("caper", "robbery plot"),
    ),
    TaxonomyEntry(
        identifier="quest",
        label="Quest",
        synonyms=("journey", "mission"),
    ),
    TaxonomyEntry(
        identifier="political-intrigue",
        label="Political Intrigue",
        synonyms=("court politics", "conspiracy"),
    ),
    TaxonomyEntry(
        identifier="war",
        label="War",
        synonyms=("military conflict",),
    ),
    TaxonomyEntry(
        identifier="murder-investigation",
        label="Murder Investigation",
        synonyms=("detective case", "criminal investigation"),
    ),
    TaxonomyEntry(
        identifier="forbidden-love",
        label="Forbidden Love",
        synonyms=("star-crossed lovers",),
    ),
    TaxonomyEntry(
        identifier="second-chance",
        label="Second Chance",
        synonyms=("fresh start",),
    ),
    TaxonomyEntry(
        identifier="slow-burn-romance",
        label="Slow Burn Romance",
        synonyms=("slow burn",),
    ),
    TaxonomyEntry(
        identifier="time-travel",
        label="Time Travel",
        synonyms=("temporal displacement",),
    ),
    TaxonomyEntry(
        identifier="identity-secrets",
        label="Identity Secrets",
        synonyms=("hidden identity", "secret past"),
    ),
    TaxonomyEntry(
        identifier="competition",
        label="Competition",
        synonyms=("tournament", "contest"),
    ),
)


_CHARACTER_DYNAMICS: Final[tuple[TaxonomyEntry, ...]] = (
    TaxonomyEntry(
        identifier="enemies-to-lovers",
        label="Enemies to Lovers",
        synonyms=("adversaries to lovers",),
    ),
    TaxonomyEntry(
        identifier="friends-to-lovers",
        label="Friends to Lovers",
        synonyms=("best friends romance",),
    ),
    TaxonomyEntry(
        identifier="mentor-mentee",
        label="Mentor and Mentee",
        synonyms=("teacher-student",),
    ),
    TaxonomyEntry(
        identifier="rivals",
        label="Rivals",
        synonyms=("rivalry",),
    ),
    TaxonomyEntry(
        identifier="siblings",
        label="Siblings",
        synonyms=("brothers and sisters",),
    ),
    TaxonomyEntry(
        identifier="parent-child",
        label="Parent and Child",
        synonyms=("family bond",),
    ),
    TaxonomyEntry(
        identifier="partners-in-crime",
        label="Partners in Crime",
        synonyms=("criminal duo",),
    ),
    TaxonomyEntry(
        identifier="reluctant-allies",
        label="Reluctant Allies",
        synonyms=("forced alliance",),
    ),
    TaxonomyEntry(
        identifier="team-ensemble",
        label="Team Ensemble",
        synonyms=("group cast",),
    ),
    TaxonomyEntry(
        identifier="love-triangle",
        label="Love Triangle",
        synonyms=("romantic triangle",),
    ),
    TaxonomyEntry(
        identifier="grumpy-sunshine",
        label="Grumpy and Sunshine",
        synonyms=("opposites attract",),
    ),
    TaxonomyEntry(
        identifier="bodyguard-ward",
        label="Bodyguard and Ward",
        synonyms=("protector dynamic",),
    ),
    TaxonomyEntry(
        identifier="detective-suspect",
        label="Detective and Suspect",
        synonyms=("cat-and-mouse",),
    ),
)


_AGE_BANDS: Final[tuple[AgeBandEntry, ...]] = (
    AgeBandEntry(
        identifier="middle-grade",
        label="Middle Grade (8-12)",
        min_age=8,
        max_age=12,
        maturity_rating="general",
        synonyms=("children", "juvenile"),
    ),
    AgeBandEntry(
        identifier="young-adult",
        label="Young Adult (13-17)",
        min_age=13,
        max_age=17,
        maturity_rating="teen",
        synonyms=("ya", "teen"),
    ),
    AgeBandEntry(
        identifier="new-adult",
        label="New Adult (18-25)",
        min_age=18,
        max_age=25,
        maturity_rating="mature",
        synonyms=("na",),
    ),
    AgeBandEntry(
        identifier="adult",
        label="Adult (18+)",
        min_age=18,
        max_age=120,
        maturity_rating="mature",
        synonyms=("general adult",),
    ),
)


_SPICE_LEVELS: Final[tuple[SpiceLevelEntry, ...]] = (
    SpiceLevelEntry(
        identifier="spice-1-none",
        label="1 - None",
        level=1,
        maturity_rating_hint="general",
        synonyms=("clean", "fade to black"),
    ),
    SpiceLevelEntry(
        identifier="spice-2-mild",
        label="2 - Mild",
        level=2,
        maturity_rating_hint="general",
        synonyms=("subtle",),
    ),
    SpiceLevelEntry(
        identifier="spice-3-moderate",
        label="3 - Moderate",
        level=3,
        maturity_rating_hint="teen",
        synonyms=("medium",),
    ),
    SpiceLevelEntry(
        identifier="spice-4-high",
        label="4 - High",
        level=4,
        maturity_rating_hint="mature",
        synonyms=("steamy",),
    ),
    SpiceLevelEntry(
        identifier="spice-5-explicit",
        label="5 - Explicit",
        level=5,
        maturity_rating_hint="mature",
        synonyms=("open door", "erotica-adjacent"),
    ),
)


def _index_entries(
    entries: tuple[TaxonomyEntry, ...],
) -> Mapping[str, TaxonomyEntry]:
    return MappingProxyType({entry.identifier: entry for entry in entries})


def _index_age_bands(
    entries: tuple[AgeBandEntry, ...],
) -> Mapping[str, AgeBandEntry]:
    return MappingProxyType({entry.identifier: entry for entry in entries})


def _index_spice_levels(
    entries: tuple[SpiceLevelEntry, ...],
) -> Mapping[str, SpiceLevelEntry]:
    return MappingProxyType({entry.identifier: entry for entry in entries})


_GENRES_BY_ID: Final[Mapping[str, TaxonomyEntry]] = _index_entries(_GENRES)
_PLOT_TAGS_BY_ID: Final[Mapping[str, TaxonomyEntry]] = _index_entries(_PLOT_TAGS)
_CHARACTER_DYNAMICS_BY_ID: Final[Mapping[str, TaxonomyEntry]] = _index_entries(
    _CHARACTER_DYNAMICS
)
_AGE_BANDS_BY_ID: Final[Mapping[str, AgeBandEntry]] = _index_age_bands(_AGE_BANDS)
_SPICE_LEVELS_BY_ID: Final[Mapping[str, SpiceLevelEntry]] = _index_spice_levels(
    _SPICE_LEVELS
)


def get_taxonomy_version() -> str:
    """Return the fixed in-code taxonomy version identifier."""
    return TAXONOMY_VERSION


def get_all_genres() -> tuple[TaxonomyEntry, ...]:
    """Return canonical genre definitions for taxonomy v1."""
    return _GENRES


def get_genre(identifier: str) -> TaxonomyEntry | None:
    """Return a genre entry by identifier if it exists."""
    return _GENRES_BY_ID.get(identifier)


def get_all_plot_tags() -> tuple[TaxonomyEntry, ...]:
    """Return canonical plot-tag definitions for taxonomy v1."""
    return _PLOT_TAGS


def get_plot_tag(identifier: str) -> TaxonomyEntry | None:
    """Return a plot-tag entry by identifier if it exists."""
    return _PLOT_TAGS_BY_ID.get(identifier)


def get_all_character_dynamics() -> tuple[TaxonomyEntry, ...]:
    """Return canonical character-dynamic definitions for taxonomy v1."""
    return _CHARACTER_DYNAMICS


def get_character_dynamic(identifier: str) -> TaxonomyEntry | None:
    """Return a character-dynamic entry by identifier if it exists."""
    return _CHARACTER_DYNAMICS_BY_ID.get(identifier)


def get_age_bands() -> tuple[AgeBandEntry, ...]:
    """Return canonical age-band definitions for taxonomy v1."""
    return _AGE_BANDS


def get_age_band(identifier: str) -> AgeBandEntry | None:
    """Return an age-band entry by identifier if it exists."""
    return _AGE_BANDS_BY_ID.get(identifier)


def get_spice_levels() -> tuple[SpiceLevelEntry, ...]:
    """Return the canonical ordered spice scale from 1 to 5."""
    return _SPICE_LEVELS


def get_spice_level(identifier: str) -> SpiceLevelEntry | None:
    """Return a spice-level entry by identifier if it exists."""
    return _SPICE_LEVELS_BY_ID.get(identifier)


def get_spice_level_by_rank(level: int) -> SpiceLevelEntry | None:
    """Return a spice-level entry by numeric rank on the 1-5 scale."""
    if level < 1 or level > 5:
        return None
    return _SPICE_LEVELS[level - 1]


__all__ = [
    "AgeBandEntry",
    "SpiceLevelEntry",
    "TAXONOMY_VERSION",
    "TaxonomyEntry",
    "get_age_band",
    "get_age_bands",
    "get_all_character_dynamics",
    "get_all_genres",
    "get_all_plot_tags",
    "get_character_dynamic",
    "get_genre",
    "get_plot_tag",
    "get_spice_level",
    "get_spice_level_by_rank",
    "get_spice_levels",
    "get_taxonomy_version",
]
