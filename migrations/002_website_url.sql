-- v0.2: profile gains a website_url so the setup form can auto-derive the
-- business context via Claude (instead of asking the user to write it).
-- Idempotent: safe to re-run.

ALTER TABLE reels_profiles
  ADD COLUMN IF NOT EXISTS website_url VARCHAR(500) NULL AFTER ig_handle;
