-- reels-analyzer v0.1 schema (MySQL 8+).
-- Idempotent: safe to re-run.

-- One profile per member (one row).
CREATE TABLE IF NOT EXISTS reels_profiles (
  email VARCHAR(320) NOT NULL PRIMARY KEY,
  ig_handle VARCHAR(60) NOT NULL,
  business_context TEXT NOT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Handles the member tracks (their own + competitors).
CREATE TABLE IF NOT EXISTS reels_handles (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(320) NOT NULL,
  ig_handle VARCHAR(60) NOT NULL,
  kind ENUM('self','competitor') NOT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_email_handle (email, ig_handle),
  KEY email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Scraped reels cache (shared across members tracking the same handle).
CREATE TABLE IF NOT EXISTS reels_cache (
  shortcode VARCHAR(40) NOT NULL PRIMARY KEY,
  ig_handle VARCHAR(60) NOT NULL,
  caption TEXT,
  posted_at DATETIME NULL,
  duration_sec INT NULL,
  view_count INT NULL,
  like_count INT NULL,
  comment_count INT NULL,
  video_url TEXT,
  audio_url TEXT,
  raw_json JSON,
  scraped_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ig_handle_posted (ig_handle, posted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Transcripts (one per reel, cached).
CREATE TABLE IF NOT EXISTS reels_transcripts (
  shortcode VARCHAR(40) NOT NULL PRIMARY KEY,
  transcript MEDIUMTEXT NOT NULL,
  duration_sec FLOAT,
  transcribed_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Generated reports.
CREATE TABLE IF NOT EXISTS reels_reports (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(320) NOT NULL,
  status ENUM('pending','running','done','failed') NOT NULL DEFAULT 'pending',
  status_detail TEXT,
  body MEDIUMTEXT,
  meta_json JSON,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP NULL,
  KEY email_created (email, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
