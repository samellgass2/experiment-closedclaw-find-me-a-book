-- find-me-a-book
-- Initial MySQL/MariaDB schema for catalog data and user preference filters.

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL,
  password_hash TEXT NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
  preferred_language CHAR(2) NOT NULL DEFAULT 'en',
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY ux_users_email (email),
  CONSTRAINT chk_users_display_name
    CHECK (CHAR_LENGTH(display_name) >= 2),
  CONSTRAINT chk_users_preferred_language
    CHECK (preferred_language REGEXP '^[a-z]{2}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS books (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title TEXT NOT NULL,
  subtitle TEXT,
  description TEXT,
  isbn_10 CHAR(10),
  isbn_13 CHAR(13),
  publication_date DATE,
  page_count INT,
  language_code CHAR(2) NOT NULL DEFAULT 'en',
  average_rating DECIMAL(3,2),
  ratings_count INT NOT NULL DEFAULT 0,
  maturity_rating VARCHAR(16) NOT NULL DEFAULT 'general',
  publisher TEXT,
  cover_image_url TEXT,
  source_provider VARCHAR(50) NOT NULL DEFAULT 'manual',
  external_source_id VARCHAR(120),
  taxonomy_version VARCHAR(16),
  canonical_genres JSON,
  canonical_plot_tags JSON,
  canonical_character_dynamics JSON,
  age_band VARCHAR(32),
  spice_level VARCHAR(32),
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY ux_books_isbn_10 (isbn_10),
  UNIQUE KEY ux_books_isbn_13 (isbn_13),
  UNIQUE KEY ux_books_provider_external_id (
    source_provider,
    external_source_id
  ),
  INDEX ix_books_title (title(255)),
  INDEX ix_books_maturity_updated_id (maturity_rating, updated_at, id),
  INDEX ix_books_updated_id (updated_at, id),
  INDEX ix_books_age_band (age_band),
  INDEX ix_books_spice_level (spice_level),
  FULLTEXT KEY ftx_books_title_description (title, description),
  INDEX ix_books_publication_date (publication_date),
  INDEX ix_books_average_rating (average_rating),
  CONSTRAINT chk_books_isbn_10 CHECK (
    isbn_10 IS NULL OR isbn_10 REGEXP '^[0-9X]{10}$'
  ),
  CONSTRAINT chk_books_isbn_13 CHECK (
    isbn_13 IS NULL OR isbn_13 REGEXP '^[0-9]{13}$'
  ),
  CONSTRAINT chk_books_page_count CHECK (
    page_count IS NULL OR page_count > 0
  ),
  CONSTRAINT chk_books_average_rating CHECK (
    average_rating IS NULL OR (average_rating >= 0 AND average_rating <= 5)
  ),
  CONSTRAINT chk_books_ratings_count CHECK (ratings_count >= 0),
  CONSTRAINT chk_books_language_code
    CHECK (language_code REGEXP '^[a-z]{2}$'),
  CONSTRAINT chk_books_maturity_rating
    CHECK (maturity_rating IN ('general', 'teen', 'mature'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS authors (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name TEXT NOT NULL,
  sort_name TEXT,
  bio TEXT,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY ux_authors_full_name (full_name(255)),
  INDEX ix_authors_full_name_prefix (full_name(255)),
  INDEX ix_authors_sort_name (sort_name(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS genres (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code VARCHAR(40) NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY ux_genres_code (code),
  UNIQUE KEY ux_genres_display_name (display_name),
  INDEX ix_genres_lookup (code, display_name),
  CONSTRAINT chk_genres_code CHECK (code REGEXP '^[a-z0-9-]+$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_filters (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  filter_name VARCHAR(80) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  include_mature BOOLEAN NOT NULL DEFAULT FALSE,
  min_rating DECIMAL(2,1),
  max_page_count INT,
  min_publication_year SMALLINT,
  max_publication_year SMALLINT,
  language_code CHAR(2),
  sort_by VARCHAR(32) NOT NULL DEFAULT 'relevance',
  sort_direction VARCHAR(4) NOT NULL DEFAULT 'DESC',
  default_user_id BIGINT UNSIGNED AS (
    CASE WHEN is_default THEN user_id ELSE NULL END
  ) STORED,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  INDEX ix_user_filters_user_id (user_id, created_at),
  UNIQUE KEY ux_user_filters_default_per_user (default_user_id),
  CONSTRAINT fk_user_filters_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT chk_user_filters_filter_name
    CHECK (CHAR_LENGTH(filter_name) >= 1),
  CONSTRAINT chk_user_filters_min_rating CHECK (
    min_rating IS NULL OR (min_rating >= 0 AND min_rating <= 5)
  ),
  CONSTRAINT chk_user_filters_max_page_count CHECK (
    max_page_count IS NULL OR max_page_count > 0
  ),
  CONSTRAINT chk_user_filters_min_year CHECK (
    min_publication_year IS NULL
    OR min_publication_year BETWEEN 1400 AND 2100
  ),
  CONSTRAINT chk_user_filters_max_year CHECK (
    max_publication_year IS NULL
    OR max_publication_year BETWEEN 1400 AND 2100
  ),
  CONSTRAINT chk_user_filters_year_range CHECK (
    min_publication_year IS NULL
    OR max_publication_year IS NULL
    OR min_publication_year <= max_publication_year
  ),
  CONSTRAINT chk_user_filters_language_code CHECK (
    language_code IS NULL OR language_code REGEXP '^[a-z]{2}$'
  ),
  CONSTRAINT chk_user_filters_sort_by CHECK (
    sort_by IN (
      'relevance',
      'title',
      'publication_date',
      'average_rating',
      'page_count'
    )
  ),
  CONSTRAINT chk_user_filters_sort_direction
    CHECK (sort_direction IN ('ASC', 'DESC'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS book_authors (
  book_id BIGINT UNSIGNED NOT NULL,
  author_id BIGINT UNSIGNED NOT NULL,
  author_order SMALLINT NOT NULL DEFAULT 1,
  role VARCHAR(24) NOT NULL DEFAULT 'author',
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (book_id, author_id),
  INDEX ix_book_authors_author_id (author_id, book_id),
  CONSTRAINT fk_book_authors_book
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
  CONSTRAINT fk_book_authors_author
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE RESTRICT,
  CONSTRAINT chk_book_authors_order CHECK (author_order > 0),
  CONSTRAINT chk_book_authors_role CHECK (
    role IN ('author', 'editor', 'illustrator', 'translator')
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS book_genres (
  book_id BIGINT UNSIGNED NOT NULL,
  genre_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (book_id, genre_id),
  INDEX ix_book_genres_book_id (book_id),
  INDEX ix_book_genres_genre_id (genre_id, book_id),
  CONSTRAINT fk_book_genres_book
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
  CONSTRAINT fk_book_genres_genre
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_filter_genres (
  filter_id BIGINT UNSIGNED NOT NULL,
  genre_id BIGINT UNSIGNED NOT NULL,
  mode VARCHAR(8) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (filter_id, genre_id, mode),
  INDEX ix_user_filter_genres_genre_mode (genre_id, mode),
  CONSTRAINT fk_user_filter_genres_filter
    FOREIGN KEY (filter_id) REFERENCES user_filters(id) ON DELETE CASCADE,
  CONSTRAINT fk_user_filter_genres_genre
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE,
  CONSTRAINT chk_user_filter_genres_mode CHECK (mode IN ('include', 'exclude'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_filter_authors (
  filter_id BIGINT UNSIGNED NOT NULL,
  author_id BIGINT UNSIGNED NOT NULL,
  mode VARCHAR(8) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (filter_id, author_id, mode),
  INDEX ix_user_filter_authors_author_mode (author_id, mode),
  CONSTRAINT fk_user_filter_authors_filter
    FOREIGN KEY (filter_id) REFERENCES user_filters(id) ON DELETE CASCADE,
  CONSTRAINT fk_user_filter_authors_author
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
  CONSTRAINT chk_user_filter_authors_mode CHECK (mode IN ('include', 'exclude'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_book_feedback (
  user_id BIGINT UNSIGNED NOT NULL,
  book_id BIGINT UNSIGNED NOT NULL,
  status VARCHAR(16) NOT NULL,
  rating DECIMAL(2,1),
  noted_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (user_id, book_id),
  INDEX ix_user_book_feedback_book_id (book_id),
  INDEX ix_user_book_feedback_status (status, noted_at),
  CONSTRAINT fk_user_book_feedback_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_user_book_feedback_book
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
  CONSTRAINT chk_user_book_feedback_status
    CHECK (status IN ('saved', 'hidden', 'read', 'favorite')),
  CONSTRAINT chk_user_book_feedback_rating CHECK (
    rating IS NULL OR (rating >= 0 AND rating <= 5)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
