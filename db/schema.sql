-- find-me-a-book
-- Database schema for catalog data and user preference filters.
-- Target engine: PostgreSQL 15+

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;

--
-- Shared timestamp trigger function
--
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

--
-- Users and profile preferences
--
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email CITEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
  preferred_language CHAR(2) NOT NULL DEFAULT 'en',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (char_length(display_name) >= 2),
  CHECK (preferred_language ~ '^[a-z]{2}$')
);

CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

--
-- Core book catalog
--
CREATE TABLE books (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  subtitle TEXT,
  description TEXT,
  isbn_10 CHAR(10),
  isbn_13 CHAR(13),
  publication_date DATE,
  page_count INTEGER,
  language_code CHAR(2) NOT NULL DEFAULT 'en',
  average_rating NUMERIC(3,2),
  ratings_count INTEGER NOT NULL DEFAULT 0,
  maturity_rating VARCHAR(16) NOT NULL DEFAULT 'general',
  publisher TEXT,
  cover_image_url TEXT,
  source_provider VARCHAR(50) NOT NULL DEFAULT 'manual',
  external_source_id VARCHAR(120),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (isbn_10 IS NULL OR isbn_10 ~ '^[0-9X]{10}$'),
  CHECK (isbn_13 IS NULL OR isbn_13 ~ '^[0-9]{13}$'),
  CHECK (page_count IS NULL OR page_count > 0),
  CHECK (average_rating IS NULL OR (average_rating >= 0 AND average_rating <= 5)),
  CHECK (ratings_count >= 0),
  CHECK (language_code ~ '^[a-z]{2}$'),
  CHECK (maturity_rating IN ('general', 'teen', 'mature'))
);

CREATE UNIQUE INDEX ux_books_isbn_10 ON books (isbn_10) WHERE isbn_10 IS NOT NULL;
CREATE UNIQUE INDEX ux_books_isbn_13 ON books (isbn_13) WHERE isbn_13 IS NOT NULL;
CREATE UNIQUE INDEX ux_books_provider_external_id
  ON books (source_provider, external_source_id)
  WHERE external_source_id IS NOT NULL;

CREATE INDEX ix_books_title_trgm_like ON books (title);
CREATE INDEX ix_books_publication_date ON books (publication_date DESC);
CREATE INDEX ix_books_average_rating ON books (average_rating DESC);

CREATE TRIGGER trg_books_set_updated_at
BEFORE UPDATE ON books
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

--
-- Lookup and relationship tables
--
CREATE TABLE authors (
  id BIGSERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  sort_name TEXT,
  bio TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (full_name)
);

CREATE INDEX ix_authors_sort_name ON authors (sort_name);

CREATE TRIGGER trg_authors_set_updated_at
BEFORE UPDATE ON authors
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE book_authors (
  book_id BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  author_id BIGINT NOT NULL REFERENCES authors(id) ON DELETE RESTRICT,
  author_order SMALLINT NOT NULL DEFAULT 1,
  role VARCHAR(24) NOT NULL DEFAULT 'author',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (book_id, author_id),
  CHECK (author_order > 0),
  CHECK (role IN ('author', 'editor', 'illustrator', 'translator'))
);

CREATE INDEX ix_book_authors_author_id ON book_authors (author_id, book_id);

CREATE TABLE genres (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(40) NOT NULL UNIQUE,
  display_name VARCHAR(80) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (code ~ '^[a-z0-9-]+$')
);

CREATE TABLE book_genres (
  book_id BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  genre_id BIGINT NOT NULL REFERENCES genres(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (book_id, genre_id)
);

CREATE INDEX ix_book_genres_genre_id ON book_genres (genre_id, book_id);

--
-- User filter profiles: saved criteria for recommendation queries
--
CREATE TABLE user_filters (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filter_name VARCHAR(80) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  include_mature BOOLEAN NOT NULL DEFAULT FALSE,
  min_rating NUMERIC(2,1),
  max_page_count INTEGER,
  min_publication_year SMALLINT,
  max_publication_year SMALLINT,
  language_code CHAR(2),
  sort_by VARCHAR(32) NOT NULL DEFAULT 'relevance',
  sort_direction VARCHAR(4) NOT NULL DEFAULT 'DESC',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (char_length(filter_name) >= 1),
  CHECK (min_rating IS NULL OR (min_rating >= 0 AND min_rating <= 5)),
  CHECK (max_page_count IS NULL OR max_page_count > 0),
  CHECK (min_publication_year IS NULL OR min_publication_year BETWEEN 1400 AND 2100),
  CHECK (max_publication_year IS NULL OR max_publication_year BETWEEN 1400 AND 2100),
  CHECK (
    min_publication_year IS NULL OR max_publication_year IS NULL
    OR min_publication_year <= max_publication_year
  ),
  CHECK (language_code IS NULL OR language_code ~ '^[a-z]{2}$'),
  CHECK (sort_by IN ('relevance', 'title', 'publication_date', 'average_rating', 'page_count')),
  CHECK (sort_direction IN ('ASC', 'DESC'))
);

CREATE UNIQUE INDEX ux_user_filters_default_per_user
  ON user_filters (user_id)
  WHERE is_default = TRUE;

CREATE INDEX ix_user_filters_user_id ON user_filters (user_id, created_at DESC);

CREATE TRIGGER trg_user_filters_set_updated_at
BEFORE UPDATE ON user_filters
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Selected/blocked genres for a filter profile.
CREATE TABLE user_filter_genres (
  filter_id BIGINT NOT NULL REFERENCES user_filters(id) ON DELETE CASCADE,
  genre_id BIGINT NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
  mode VARCHAR(8) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (filter_id, genre_id, mode),
  CHECK (mode IN ('include', 'exclude'))
);

CREATE INDEX ix_user_filter_genres_genre_mode
  ON user_filter_genres (genre_id, mode);

-- Selected/blocked authors for a filter profile.
CREATE TABLE user_filter_authors (
  filter_id BIGINT NOT NULL REFERENCES user_filters(id) ON DELETE CASCADE,
  author_id BIGINT NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
  mode VARCHAR(8) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (filter_id, author_id, mode),
  CHECK (mode IN ('include', 'exclude'))
);

CREATE INDEX ix_user_filter_authors_author_mode
  ON user_filter_authors (author_id, mode);

--
-- Optional user/book interactions for future recommendation quality signals
--
CREATE TABLE user_book_feedback (
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  book_id BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  status VARCHAR(16) NOT NULL,
  rating NUMERIC(2,1),
  noted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, book_id),
  CHECK (status IN ('saved', 'hidden', 'read', 'favorite')),
  CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5))
);

CREATE INDEX ix_user_book_feedback_status ON user_book_feedback (status, noted_at DESC);

CREATE TRIGGER trg_user_book_feedback_set_updated_at
BEFORE UPDATE ON user_book_feedback
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
