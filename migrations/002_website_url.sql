-- v0.2: profile gains a website_url so the setup form can auto-derive the
-- business context via Claude (instead of asking the user to write it).
-- Idempotent — uses information_schema check since MySQL 8 doesn't support
-- `ADD COLUMN IF NOT EXISTS` (that's PostgreSQL-only).

SET @c = (SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema = DATABASE()
            AND table_name   = 'reels_profiles'
            AND column_name  = 'website_url');
SET @sql = IF(@c = 0,
  'ALTER TABLE reels_profiles ADD COLUMN website_url VARCHAR(500) NULL AFTER ig_handle',
  'SELECT ''website_url already exists'' AS note');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
