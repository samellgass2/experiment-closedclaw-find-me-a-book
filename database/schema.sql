-- Database schema for find-me-a-book
-- Dialect: PostgreSQL 15+
-- Purpose: Store catalog data, user profiles, and recommendation filters.

BEGIN;

-- Extensions
CREATE EXTENSION IF NOT EXISTS citext;

-- Enumerations
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reading_status') THEN
    CREATE TYPE reading_status AS ENUM (
      'wishlist',
      'reading',
      'completed',
      'paused',
      'dropped'
    );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'book_format') THEN
    CREATE TYPE book_format AS ENUM (
      'hardcover',
      'paperback',
      'ebook',
      'audiobook'
    );
  END IF;
END $$;

-- Users
CREATE TABLE IF NOT EXISTS users (
  user_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email              CITEXT NOT NULL UNIQUE,
  username           VARCHAR(32) NOT NULL UNIQUE,
  display_name       VARCHAR(120) NOT NULL,
  country_code       CHAR(2),
  birth_year         SMALLINT,
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at         TIMESTAMPTZ,
  CHECK (birth_year IS NULL OR birth_year BETWEEN 1900 AND EXTRACT(YEAR FROM NOW())::SMALLINT),
  CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$')
);

CREATE INDEX IF NOT EXISTS idx_users_active_created
  ON users (is_active, created_at DESC)
  WHERE deleted_at IS NULL;

-- Authors
CREATE TABLE IF NOT EXISTS authors (
  author_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  full_name          VARCHAR(180) NOT NULL,
  normalized_name    VARCHAR(180) NOT NULL,
  bio                TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (normalized_name)
);

CREATE INDEX IF NOT EXISTS idx_authors_name
  ON authors (normalized_name);

-- Genres
CREATE TABLE IF NOT EXISTS genres (
  genre_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug               VARCHAR(64) NOT NULL UNIQUE,
  label              VARCHAR(80) NOT NULL UNIQUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Books
CREATE TABLE IF NOT EXISTS books (
  book_id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  isbn_10                    VARCHAR(10),
  isbn_13                    VARCHAR(13),
  title                      VARCHAR(255) NOT NULL,
  subtitle                   VARCHAR(255),
  description                TEXT,
  publication_date           DATE,
  page_count                 INTEGER,
  language_code              VARCHAR(8) NOT NULL DEFAULT 'en',
  average_rating             NUMERIC(3,2),
  ratings_count              INTEGER NOT NULL DEFAULT 0,
  maturity_rating            VARCHAR(16),
  is_series                  BOOLEAN NOT NULL DEFAULT FALSE,
  cover_image_url            TEXT,
  created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (page_count IS NULL OR page_count > 0),
  CHECK (ratings_count >= 0),
  CHECK (average_rating IS NULL OR (average_rating >= 0 AND average_rating <= 5)),
  CHECK (isbn_10 IS NULL OR isbn_10 ~ '^[0-9X]{10}$'),
  CHECK (isbn_13 IS NULL OR isbn_13 ~ '^[0-9]{13}$')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_books_isbn_10
  ON books (isbn_10)
  WHERE isbn_10 IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_books_isbn_13
  ON books (isbn_13)
  WHERE isbn_13 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_books_title
  ON books (title);

CREATE INDEX IF NOT EXISTS idx_books_pubdate
  ON books (publication_date DESC);

CREATE INDEX IF NOT EXISTS idx_books_rating
  ON books (average_rating DESC, ratings_count DESC);

-- Book-author relationship (many-to-many)
CREATE TABLE IF NOT EXISTS book_authors (
  book_id             BIGINT NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
  author_id           BIGINT NOT NULL REFERENCES authors(author_id) ON DELETE RESTRICT,
  contribution_order  SMALLINT NOT NULL DEFAULT 1,
  role                VARCHAR(32) NOT NULL DEFAULT 'author',
  PRIMARY KEY (book_id, author_id, role),
  CHECK (contribution_order > 0)
);

CREATE INDEX IF NOT EXISTS idx_book_authors_author
  ON book_authors (author_id, contribution_order);

-- Book-genre relationship (many-to-many)
CREATE TABLE IF NOT EXISTS book_genres (
  book_id             BIGINT NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
  genre_id            BIGINT NOT NULL REFERENCES genres(genre_id) ON DELETE RESTRICT,
  weight              NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
  PRIMARY KEY (book_id, genre_id),
  CHECK (weight > 0 AND weight <= 1)
);

CREATE INDEX IF NOT EXISTS idx_book_genres_genre
  ON book_genres (genre_id);

-- User bookshelf / interaction state
CREATE TABLE IF NOT EXISTS user_books (
  user_id             BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  book_id             BIGINT NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
  status              reading_status NOT NULL DEFAULT 'wishlist',
  user_rating         NUMERIC(2,1),
  review_text         TEXT,
  started_at          DATE,
  finished_at         DATE,
  added_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, book_id),
  CHECK (user_rating IS NULL OR (user_rating >= 0.5 AND user_rating <= 5.0)),
  CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_user_books_status
  ON user_books (user_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_books_book
  ON user_books (book_id);

-- Filters table (required): user-defined recommendation filter profiles.
CREATE TABLE IF NOT EXISTS filters (
  filter_id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id                     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  name                        VARCHAR(80) NOT NULL,
  include_read_books          BOOLEAN NOT NULL DEFAULT FALSE,
  min_publication_year        SMALLINT,
  max_publication_year        SMALLINT,
  min_page_count              INTEGER,
  max_page_count              INTEGER,
  min_average_rating          NUMERIC(3,2),
  language_codes              TEXT[] NOT NULL DEFAULT ARRAY['en']::TEXT[],
  allowed_formats             book_format[] NOT NULL DEFAULT ARRAY['hardcover','paperback','ebook','audiobook']::book_format[],
  excluded_author_ids         BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[],
  blocked_maturity_ratings    TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  sort_by                     VARCHAR(24) NOT NULL DEFAULT 'relevance',
  is_default                  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (min_publication_year IS NULL OR min_publication_year BETWEEN 1450 AND EXTRACT(YEAR FROM NOW())::SMALLINT),
  CHECK (max_publication_year IS NULL OR max_publication_year BETWEEN 1450 AND EXTRACT(YEAR FROM NOW())::SMALLINT + 3),
  CHECK (min_publication_year IS NULL OR max_publication_year IS NULL OR min_publication_year <= max_publication_year),
  CHECK (min_page_count IS NULL OR min_page_count > 0),
  CHECK (max_page_count IS NULL OR max_page_count > 0),
  CHECK (min_page_count IS NULL OR max_page_count IS NULL OR min_page_count <= max_page_count),
  CHECK (min_average_rating IS NULL OR (min_average_rating >= 0 AND min_average_rating <= 5)),
  CHECK (sort_by IN ('relevance','rating_desc','newest','oldest','title_asc')),
  UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_filters_user
  ON filters (user_id, updated_at DESC);

-- At most one default filter per user.
CREATE UNIQUE INDEX IF NOT EXISTS uq_filters_one_default_per_user
  ON filters (user_id)
  WHERE is_default = TRUE;

-- Filter genres: explicit include/exclude rules.
CREATE TABLE IF NOT EXISTS filter_genres (
  filter_id           BIGINT NOT NULL REFERENCES filters(filter_id) ON DELETE CASCADE,
  genre_id            BIGINT NOT NULL REFERENCES genres(genre_id) ON DELETE RESTRICT,
  match_mode          VARCHAR(8) NOT NULL DEFAULT 'include',
  PRIMARY KEY (filter_id, genre_id, match_mode),
  CHECK (match_mode IN ('include', 'exclude'))
);

CREATE INDEX IF NOT EXISTS idx_filter_genres_filter
  ON filter_genres (filter_id, match_mode);

-- Optional denormalized search view for recommendation candidate ranking.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_book_search AS
SELECT
  b.book_id,
  b.title,
  b.subtitle,
  b.publication_date,
  b.page_count,
  b.language_code,
  b.average_rating,
  b.ratings_count,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT g.slug), NULL) AS genre_slugs,
  STRING_AGG(DISTINCT a.full_name, ', ' ORDER BY a.full_name) AS author_names
FROM books b
LEFT JOIN book_genres bg ON bg.book_id = b.book_id
LEFT JOIN genres g ON g.genre_id = bg.genre_id
LEFT JOIN book_authors ba ON ba.book_id = b.book_id
LEFT JOIN authors a ON a.author_id = ba.author_id
GROUP BY b.book_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_book_search_book
  ON mv_book_search (book_id);

COMMIT;
