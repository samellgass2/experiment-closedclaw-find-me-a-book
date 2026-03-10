-- Search-oriented indexes for advanced filters and relevance ranking.

ALTER TABLE books
  ADD INDEX IF NOT EXISTS ix_books_maturity_updated_id (
    maturity_rating,
    updated_at,
    id
  ),
  ADD INDEX IF NOT EXISTS ix_books_updated_id (updated_at, id),
  ADD FULLTEXT INDEX IF NOT EXISTS ftx_books_title_description (
    title,
    description
  );

ALTER TABLE authors
  ADD INDEX IF NOT EXISTS ix_authors_full_name_prefix (full_name(255));

ALTER TABLE genres
  ADD INDEX IF NOT EXISTS ix_genres_lookup (code, display_name);

ALTER TABLE book_genres
  ADD INDEX IF NOT EXISTS ix_book_genres_book_id (book_id);
