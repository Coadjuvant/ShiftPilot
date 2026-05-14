CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    license_key TEXT,
    invite_token TEXT,
    invite_expires_at TIMESTAMPTZ,
    invite_created_by INTEGER,
    last_invite_token TEXT,
    public_id TEXT UNIQUE,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ,
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    event TEXT,
    detail TEXT,
    ip TEXT,
    ip_v4 TEXT,
    user_agent TEXT,
    location TEXT,
    created_at TIMESTAMPTZ,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS configs (
    id SERIAL PRIMARY KEY,
    owner TEXT NOT NULL,
    filename TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(owner, filename)
);

CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    owner TEXT NOT NULL UNIQUE,
    clinic_name TEXT,
    start_date DATE,
    weeks INTEGER,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
