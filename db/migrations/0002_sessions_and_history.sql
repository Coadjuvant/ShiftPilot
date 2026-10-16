-- Additive migration, also applied idempotently by application startup.
CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_sessions_user_idx ON auth_sessions(user_id);
CREATE TABLE IF NOT EXISTS schedule_versions (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    payload JSONB NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'published')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS schedule_versions_owner_idx ON schedule_versions(owner, created_at DESC);
INSERT INTO schedule_versions (id, owner, payload, state, created_at, published_at)
SELECT 'legacy-' || id, owner, payload, 'published', COALESCE(created_at,NOW()), COALESCE(updated_at,NOW())
FROM schedules WHERE NOT (payload ? 'version_id') ON CONFLICT(id) DO NOTHING;
CREATE TABLE IF NOT EXISTS legacy_schedule_owners (
    owner TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);
INSERT INTO legacy_schedule_owners(owner,user_id)
SELECT DISTINCT u.username,u.id FROM users u JOIN schedules s ON s.owner=u.username
WHERE u.username !~ '^[0-9]+$' ON CONFLICT(owner) DO NOTHING;
