-- Taxonomy fields required for normalized crawler ingestion payloads.

ALTER TABLE books
  ADD COLUMN IF NOT EXISTS taxonomy_version VARCHAR(16) NULL,
  ADD COLUMN IF NOT EXISTS canonical_genres JSON NULL,
  ADD COLUMN IF NOT EXISTS canonical_plot_tags JSON NULL,
  ADD COLUMN IF NOT EXISTS canonical_character_dynamics JSON NULL,
  ADD COLUMN IF NOT EXISTS age_band VARCHAR(32) NULL,
  ADD COLUMN IF NOT EXISTS spice_level VARCHAR(32) NULL;

ALTER TABLE books
  ADD INDEX IF NOT EXISTS ix_books_age_band (age_band),
  ADD INDEX IF NOT EXISTS ix_books_spice_level (spice_level);
