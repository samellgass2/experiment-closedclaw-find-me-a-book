"""Framework-agnostic backend filtering criteria and query utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, TypedDict

DEFAULT_BOOK_LIMIT = 20
SPICE_LEVEL_TO_MATURITY_RATING: dict[str, str] = {
    "low": "general",
    "medium": "teen",
    "high": "mature",
}
MATURITY_TO_SPICE_LEVEL: dict[str, str] = {
    "general": "low",
    "teen": "medium",
    "mature": "high",
}
AGE_RATING_ALIASES: dict[str, str] = {
    "general": "general",
    "kids": "general",
    "teen": "teen",
    "ya": "teen",
    "mature": "mature",
    "adult": "mature",
}
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")

QUERY_EXACT_TITLE_WEIGHT = 160
QUERY_TITLE_PREFIX_WEIGHT = 100
QUERY_TITLE_CONTAINS_WEIGHT = 55
QUERY_AUTHOR_WEIGHT = 45
QUERY_FULLTEXT_WEIGHT = 80
GENRE_WEIGHT = 30
AGE_RATING_WEIGHT = 22
SPICE_WEIGHT = 18
SUBJECT_MATCH_WEIGHT = 10
PLOT_POINT_MATCH_WEIGHT = 8
CHARACTER_DYNAMIC_WEIGHT = 7
MAX_TERM_OCCURRENCE_MULTIPLIER = 3

MATURITY_MIN_AGE_SQL = (
    "CASE b.maturity_rating "
    "WHEN 'general' THEN 0 "
    "WHEN 'teen' THEN 13 "
    "WHEN 'mature' THEN 18 "
    "ELSE 0 END"
)
MATURITY_MAX_AGE_SQL = (
    "CASE b.maturity_rating "
    "WHEN 'general' THEN 12 "
    "WHEN 'teen' THEN 17 "
    "WHEN 'mature' THEN 120 "
    "ELSE 120 END"
)

BOOK_SELECT_FROM_CANDIDATES_SQL = """
SELECT
  cb.id AS id,
  cb.title AS title,
  COALESCE(
    (
      SELECT GROUP_CONCAT(
        DISTINCT a.full_name
        ORDER BY ba.author_order
        SEPARATOR ', '
      )
      FROM book_authors ba
      INNER JOIN authors a ON a.id = ba.author_id
      WHERE ba.book_id = cb.id
    ),
    'Unknown Author'
  ) AS author,
  (
    SELECT GROUP_CONCAT(
      DISTINCT g.display_name
      ORDER BY g.display_name
      SEPARATOR ', '
    )
    FROM book_genres bg
    INNER JOIN genres g ON g.id = bg.genre_id
    WHERE bg.book_id = cb.id
  ) AS genre,
  cb.maturity_rating AS age_rating,
  cb.description AS description,
  cb.average_rating AS average_rating,
  cb.ratings_count AS ratings_count,
  cb.relevance_score AS relevance_score
FROM candidate_books cb
""".strip()


class BookPayload(TypedDict):
    """JSON-serializable book data returned by API endpoints."""

    id: int
    title: str
    author: str
    genre: str | None
    age_rating: str
    spice_level: str
    summary: str | None
    description: str | None
    subject_matter: list[str]
    plot_points: list[str]
    character_dynamics: list[str]


@dataclass(frozen=True)
class BookFilterCriteria:
    """Filter and ranking parameters for advanced backend queries."""

    query: str | None = None
    genre: str | None = None
    age_rating: str | None = None
    subject_matter: tuple[str, ...] = field(default_factory=tuple)
    plot_points: tuple[str, ...] = field(default_factory=tuple)
    character_dynamics: tuple[str, ...] = field(default_factory=tuple)
    spice_level: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    limit: int = DEFAULT_BOOK_LIMIT


def build_book_filter_query(
    criteria: BookFilterCriteria,
) -> tuple[str, tuple[Any, ...]]:
    """Build a parameterized SQL query plus placeholder values.

    Ranking priority is encoded by weight constants:
    1. genre + age_rating (highest)
    2. subject_matter + spice_level
    3. plot_points + character_dynamics
    """
    where_clauses: list[str] = []
    relevance_terms: list[str] = []
    relevance_params: list[Any] = []
    where_params: list[Any] = []

    query = criteria.query
    has_query = query is not None and query.strip() != ""

    if has_query:
        assert query is not None
        normalized_query = query.strip()
        like_pattern = f"%{normalized_query}%"
        prefix_pattern = f"{normalized_query}%"
        boolean_query = to_boolean_prefix_query(normalized_query)

        relevance_terms.extend(
            [
                (
                    "CASE WHEN LOWER(b.title) = LOWER(%s) "
                    f"THEN {QUERY_EXACT_TITLE_WEIGHT} ELSE 0 END"
                ),
                (
                    "CASE WHEN b.title LIKE %s "
                    f"THEN {QUERY_TITLE_PREFIX_WEIGHT} ELSE 0 END"
                ),
                (
                    "CASE WHEN b.title LIKE %s "
                    f"THEN {QUERY_TITLE_CONTAINS_WEIGHT} ELSE 0 END"
                ),
                (
                    "CASE WHEN EXISTS ("
                    "SELECT 1 "
                    "FROM book_authors qa "
                    "INNER JOIN authors qauthor "
                    "ON qauthor.id = qa.author_id "
                    "WHERE qa.book_id = b.id "
                    "AND qauthor.full_name LIKE %s"
                    ") "
                    f"THEN {QUERY_AUTHOR_WEIGHT} ELSE 0 END"
                ),
                (
                    "CASE WHEN MATCH(b.title, b.description) "
                    "AGAINST (%s IN BOOLEAN MODE) > 0 "
                    f"THEN {QUERY_FULLTEXT_WEIGHT} ELSE 0 END"
                ),
            ]
        )
        where_clauses.append(
            "("  # Keep one grouped query predicate for clearer EXPLAIN plans.
            "b.title LIKE %s "
            "OR b.description LIKE %s "
            "OR MATCH(b.title, b.description) "
            "AGAINST (%s IN BOOLEAN MODE) "
            "OR EXISTS ("
            "SELECT 1 "
            "FROM book_authors qba "
            "INNER JOIN authors qa ON qa.id = qba.author_id "
            "WHERE qba.book_id = b.id "
            "AND qa.full_name LIKE %s"
            ")"
            ")"
        )
        relevance_params.extend(
            [
                normalized_query,
                prefix_pattern,
                like_pattern,
                like_pattern,
                boolean_query,
            ]
        )
        where_params.extend(
            [
                like_pattern,
                like_pattern,
                boolean_query,
                like_pattern,
            ]
        )

    genre = criteria.genre
    if genre is not None:
        genre_filter_sql = genre_exists_sql()
        where_clauses.append(genre_filter_sql)
        where_params.extend([genre, genre])
        relevance_terms.append(
            (
                "CASE WHEN "
                f"{genre_filter_sql} "
                f"THEN {GENRE_WEIGHT} ELSE 0 END"
            )
        )
        relevance_params.extend([genre, genre])

    age_rating = criteria.age_rating
    if age_rating is not None:
        normalized_age_rating = AGE_RATING_ALIASES.get(age_rating.lower())
        if normalized_age_rating is not None:
            where_clauses.append("b.maturity_rating = %s")
            where_params.append(normalized_age_rating)
            relevance_terms.append(
                (
                    "CASE WHEN b.maturity_rating = %s "
                    f"THEN {AGE_RATING_WEIGHT} ELSE 0 END"
                )
            )
            relevance_params.append(normalized_age_rating)

    for subject_matter in criteria.subject_matter:
        where_clauses.append(
            "b.description IS NOT NULL "
            "AND LOWER(b.description) LIKE LOWER(%s)"
        )
        where_params.append(f"%{subject_matter}%")
        relevance_terms.append(description_occurrence_score_sql(SUBJECT_MATCH_WEIGHT))
        relevance_params.extend([subject_matter, subject_matter])

    for plot_point in criteria.plot_points:
        where_clauses.append(
            "b.description IS NOT NULL "
            "AND LOWER(b.description) LIKE LOWER(%s)"
        )
        where_params.append(f"%{plot_point}%")
        relevance_terms.append(description_occurrence_score_sql(PLOT_POINT_MATCH_WEIGHT))
        relevance_params.extend([plot_point, plot_point])

    for dynamic in criteria.character_dynamics:
        where_clauses.append(
            "b.description IS NOT NULL "
            "AND LOWER(b.description) LIKE LOWER(%s)"
        )
        where_params.append(f"%{dynamic}%")
        relevance_terms.append(
            description_occurrence_score_sql(CHARACTER_DYNAMIC_WEIGHT)
        )
        relevance_params.extend([dynamic, dynamic])

    spice_level = criteria.spice_level
    if spice_level is not None:
        maturity_rating = SPICE_LEVEL_TO_MATURITY_RATING[spice_level]
        where_clauses.append("b.maturity_rating = %s")
        where_params.append(maturity_rating)
        relevance_terms.append(
            (
                "CASE WHEN b.maturity_rating = %s "
                f"THEN {SPICE_WEIGHT} ELSE 0 END"
            )
        )
        relevance_params.append(maturity_rating)

    age_min = criteria.age_min
    if age_min is not None:
        where_clauses.append(f"{MATURITY_MAX_AGE_SQL} >= %s")
        where_params.append(age_min)

    age_max = criteria.age_max
    if age_max is not None:
        where_clauses.append(f"{MATURITY_MIN_AGE_SQL} <= %s")
        where_params.append(age_max)

    relevance_sql = " + ".join(relevance_terms) if relevance_terms else "0"
    has_relevance = bool(relevance_terms)

    candidate_query: list[str] = [
        "WITH candidate_books AS (",
        "  SELECT",
        "    b.id AS id,",
        "    b.title AS title,",
        "    b.maturity_rating AS maturity_rating,",
        "    b.description AS description,",
        "    b.average_rating AS average_rating,",
        "    b.ratings_count AS ratings_count,",
        "    b.updated_at AS updated_at,",
        f"    ({relevance_sql}) AS relevance_score",
        "  FROM books b",
    ]
    if where_clauses:
        candidate_query.append("  WHERE " + " AND ".join(where_clauses))

    if has_relevance:
        candidate_query.append(
            "  ORDER BY relevance_score DESC, "
            "COALESCE(b.average_rating, 0) DESC, "
            "b.ratings_count DESC, b.updated_at DESC, b.id DESC"
        )
    else:
        candidate_query.append(
            "  ORDER BY COALESCE(b.average_rating, 0) DESC, "
            "b.ratings_count DESC, b.updated_at DESC, b.id DESC"
        )
    candidate_query.append("  LIMIT %s")
    candidate_query.append(")")

    outer_query = [
        *candidate_query,
        BOOK_SELECT_FROM_CANDIDATES_SQL,
    ]
    if has_relevance:
        outer_query.append(
            "ORDER BY cb.relevance_score DESC, "
            "COALESCE(cb.average_rating, 0) DESC, "
            "cb.ratings_count DESC, cb.updated_at DESC, cb.id DESC"
        )
    else:
        outer_query.append(
            "ORDER BY COALESCE(cb.average_rating, 0) DESC, "
            "cb.ratings_count DESC, cb.updated_at DESC, cb.id DESC"
        )

    params = [*relevance_params, *where_params, criteria.limit]
    sql = "\n".join(outer_query)
    return sql, tuple(params)


def execute_book_filter_query(
    connection: Any,
    criteria: BookFilterCriteria,
) -> list[BookPayload]:
    """Execute the advanced filter query and return JSON-ready rows."""
    sql, params = build_book_filter_query(criteria)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    return [row_to_book_payload(row) for row in rows]


def row_to_book_payload(row: Mapping[str, Any]) -> BookPayload:
    """Convert a DB row mapping to a stable JSON-serializable payload."""
    description = str(row["description"]) if row.get("description") is not None else None
    age_rating = str(row["age_rating"])
    return BookPayload(
        id=int(row["id"]),
        title=str(row["title"]),
        author=str(row["author"]),
        genre=str(row["genre"]) if row.get("genre") is not None else None,
        age_rating=age_rating,
        spice_level=MATURITY_TO_SPICE_LEVEL.get(age_rating, "low"),
        summary=description,
        description=description,
        subject_matter=[],
        plot_points=[],
        character_dynamics=[],
    )


def description_occurrence_score_sql(weight: int) -> str:
    """Return SQL snippet that rewards repeated token occurrences."""
    return (
        "(LEAST("
        f"{MAX_TERM_OCCURRENCE_MULTIPLIER}, "
        "((CHAR_LENGTH(LOWER(COALESCE(b.description, ''))) "
        "- CHAR_LENGTH(REPLACE("
        "LOWER(COALESCE(b.description, '')), LOWER(%s), ''"
        "))) / NULLIF(CHAR_LENGTH(%s), 0))"
        f") * {weight})"
    )


def genre_exists_sql() -> str:
    """Return EXISTS clause for case-insensitive genre matching."""
    return (
        "EXISTS ("
        "SELECT 1 "
        "FROM book_genres filter_bg "
        "INNER JOIN genres filter_g ON filter_g.id = filter_bg.genre_id "
        "WHERE filter_bg.book_id = b.id "
        "AND ("
        "filter_g.code = %s "
        "OR filter_g.display_name = %s"
        ")"
        ")"
    )


def to_boolean_prefix_query(raw_text: str) -> str:
    """Build a boolean-mode FULLTEXT query with prefix matching."""
    tokens = TOKEN_PATTERN.findall(raw_text.lower())
    if not tokens:
        return raw_text
    return " ".join(f"+{token}*" for token in tokens)
