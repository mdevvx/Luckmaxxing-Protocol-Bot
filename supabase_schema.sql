-- ============================================================
--  Luckmaxxing Protocol — Supabase Schema
--  Version: 3.0  (channel-based flow)
--
--  Safe to run on a fresh database OR an existing one.
--  All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS.
-- ============================================================

-- ─────────────────────────────────────────────────────────────
--  0. Clean up old RLS policies
-- ─────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS "Service role has full access to enrollments"   ON enrollments;
DROP POLICY IF EXISTS "Service role has full access to guild_settings" ON guild_settings;
DROP POLICY IF EXISTS "Service role has full access to daily_progress" ON daily_progress;
DROP POLICY IF EXISTS "Service role has full access to enrollment_ids" ON enrollment_ids;

-- ─────────────────────────────────────────────────────────────
--  1. Tables
-- ─────────────────────────────────────────────────────────────

-- enrollments — one row per (user, guild)
CREATE TABLE IF NOT EXISTS enrollments (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT    NOT NULL,
    guild_id         BIGINT    NOT NULL,
    enrollment_id    TEXT      NOT NULL DEFAULT '',
    enrollment_used  BOOLEAN   NOT NULL DEFAULT FALSE,
    current_day      INTEGER   NOT NULL DEFAULT 0,
    channel_id       BIGINT,                          -- private training channel
    enrolled_at      TIMESTAMPTZ DEFAULT NOW(),
    last_message_sent TIMESTAMPTZ,
    completed        BOOLEAN   NOT NULL DEFAULT FALSE,
    UNIQUE(user_id, guild_id)
);

-- guild_settings — one row per guild
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id     BIGINT PRIMARY KEY,
    bot_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    category_id  BIGINT,          -- Discord category for training channels
    role_id      BIGINT,          -- Role assigned on enrollment
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- daily_progress — analytics log
CREATE TABLE IF NOT EXISTS daily_progress (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    guild_id     BIGINT NOT NULL,
    day_number   INTEGER NOT NULL,
    completed_at TIMESTAMPTZ DEFAULT NOW()
);

-- enrollment_ids — access-control codes
CREATE TABLE IF NOT EXISTS enrollment_ids (
    id          BIGSERIAL PRIMARY KEY,
    id_code     VARCHAR(5) NOT NULL,
    guild_id    BIGINT     NOT NULL,
    used        BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    used_by     BIGINT,
    used_at     TIMESTAMPTZ,
    UNIQUE(id_code, guild_id)
);

-- ─────────────────────────────────────────────────────────────
--  2. Migrations — add columns that might be missing on existing DBs
-- ─────────────────────────────────────────────────────────────
ALTER TABLE enrollments    ADD COLUMN IF NOT EXISTS channel_id       BIGINT;
ALTER TABLE enrollments    ADD COLUMN IF NOT EXISTS enrollment_id    TEXT NOT NULL DEFAULT '';
ALTER TABLE enrollments    ADD COLUMN IF NOT EXISTS enrollment_used  BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS category_id     BIGINT;
ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS role_id         BIGINT;

-- ─────────────────────────────────────────────────────────────
--  3. Indexes
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_enrollments_user_guild   ON enrollments(user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_guild        ON enrollments(guild_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_completed    ON enrollments(completed);
CREATE INDEX IF NOT EXISTS idx_enrollments_current_day  ON enrollments(current_day);
CREATE INDEX IF NOT EXISTS idx_enrollments_channel      ON enrollments(channel_id);
CREATE INDEX IF NOT EXISTS idx_daily_progress_user      ON daily_progress(user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_daily_progress_day       ON daily_progress(day_number);
CREATE INDEX IF NOT EXISTS idx_enrollment_ids_lookup    ON enrollment_ids(id_code, guild_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_ids_used      ON enrollment_ids(used);

-- ─────────────────────────────────────────────────────────────
--  4. RLS — disabled (service_role key bypasses it anyway)
--     This avoids the common "violates row-level security policy" error.
-- ─────────────────────────────────────────────────────────────
ALTER TABLE enrollments    DISABLE ROW LEVEL SECURITY;
ALTER TABLE guild_settings DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_progress DISABLE ROW LEVEL SECURITY;
ALTER TABLE enrollment_ids DISABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────
--  5. Permissions
-- ─────────────────────────────────────────────────────────────
GRANT ALL PRIVILEGES ON ALL TABLES   IN SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT USAGE ON SCHEMA public TO service_role;

-- ─────────────────────────────────────────────────────────────
--  6. Verification
-- ─────────────────────────────────────────────────────────────
SELECT
    table_name,
    CASE WHEN rowsecurity THEN 'RLS ON' ELSE 'RLS OFF' END AS rls
FROM information_schema.tables t
JOIN pg_tables p ON t.table_name = p.tablename AND p.schemaname = 'public'
WHERE t.table_schema = 'public'
  AND t.table_name IN ('enrollments','guild_settings','daily_progress','enrollment_ids')
ORDER BY table_name;

DO $$
BEGIN
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'Schema v3.0 applied successfully.';
    RAISE NOTICE 'Tables: enrollments, guild_settings, daily_progress, enrollment_ids';
    RAISE NOTICE 'New columns: enrollments.channel_id, guild_settings.category_id, guild_settings.role_id';
    RAISE NOTICE 'RLS: disabled on all tables';
    RAISE NOTICE '==============================================';
END $$;

ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS last_button_click TIMESTAMPTZ;

-- ─────────────────────────────────────────────────────────────
--  7. Thread-based flow (v4.0)
--     enrollments.channel_id is reused to store the private
--     THREAD id now (not a channel id). category_id above is
--     left in place but no longer used by the bot.
-- ─────────────────────────────────────────────────────────────
ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS threads_channel_id BIGINT; -- parent channel private training threads are created under
ALTER TABLE enrollments    ADD COLUMN IF NOT EXISTS dm_ack BOOLEAN NOT NULL DEFAULT FALSE; -- user completed the "report to Papi" DM ritual

-- ─────────────────────────────────────────────────────────────
--  8. Video watch tracking (v5.0)
--     Written by the external /watch page via an insert-only anon key
--     scoped to this table only. Consumed by our own background job
--     (service_role, bypasses RLS) which then advances progress.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS video_watches (
    id           BIGSERIAL PRIMARY KEY,
    token        TEXT        NOT NULL,
    day_number   INTEGER     NOT NULL,
    discord_id   BIGINT      NOT NULL,
    processed    BOOLEAN     NOT NULL DEFAULT FALSE,
    watched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_video_watches_token      ON video_watches(token);
CREATE INDEX IF NOT EXISTS idx_video_watches_discord_id ON video_watches(discord_id);
CREATE INDEX IF NOT EXISTS idx_video_watches_processed  ON video_watches(processed);

ALTER TABLE video_watches ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon can insert video watches" ON video_watches;
CREATE POLICY "anon can insert video watches"
    ON video_watches
    FOR INSERT
    TO anon
    WITH CHECK (true);
-- No SELECT/UPDATE/DELETE policy for anon: the public key can insert only.

-- ─────────────────────────────────────────────────────────────
--  9. Training video URLs (v6.0)
--     Read only by the bot's own service_role key
--     (see database/training_videos.py). Not exposed to the public key.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS training_videos (
    day_number INTEGER     PRIMARY KEY,
    url        TEXT        NOT NULL,
    caption    TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE training_videos DISABLE ROW LEVEL SECURITY;
GRANT ALL PRIVILEGES ON training_videos TO service_role;

-- Seed placeholders — replace url/caption with the real hosted links,
-- or update the rows directly in Supabase later.
INSERT INTO training_videos (day_number, url, caption) VALUES
    (1, 'https://cdn.example.com/day1.mp4', 'Today''s lesson: luck is a skill you can train. Watch the video, then lock in the mantra — I am lucky. I am the luck.'),
    (2, 'https://cdn.example.com/day2.mp4', NULL),
    (3, 'https://cdn.example.com/day3.mp4', NULL),
    (4, 'https://cdn.example.com/day4.mp4', NULL),
    (5, 'https://cdn.example.com/day5.mp4', NULL),
    (6, 'https://cdn.example.com/day6.mp4', NULL),
    (7, 'https://cdn.example.com/day7.mp4', NULL),
    (8, 'https://cdn.example.com/day8.mp4', NULL)
ON CONFLICT (day_number) DO NOTHING;