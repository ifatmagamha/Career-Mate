-- Career Mate schema v1 (PostgreSQL / Supabase).
-- Runs inside the app schema (search_path = <DB_SCHEMA>, public, extensions).
-- Every table carries user_id: the API scopes every query to the logged-in user.

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA extensions;

-- unaccent() is not IMMUTABLE, so it cannot be used in a generated column directly
CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
    AS $$ SELECT extensions.unaccent('extensions.unaccent'::regdictionary, $1) $$;

-- What the employer published (re-extractable, never edited by tracking)
CREATE TABLE offers (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL,
    url            text,
    title          text NOT NULL,
    company        text,
    location       text,
    remote_policy  text,
    contract_type  text,
    seniority      text,
    salary         text,
    deadline       date,
    skills         jsonb NOT NULL DEFAULT '[]',
    nice_to_have   jsonb NOT NULL DEFAULT '[]',
    missions       jsonb NOT NULL DEFAULT '[]',
    requirements   jsonb NOT NULL DEFAULT '[]',
    summary        text,
    raw_text       text,
    source         text,
    model          text,
    prompt_version text,
    match_score    integer,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    -- Full-text index: accents ignored, language-neutral ('simple'), title/company weigh most
    search         tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', f_unaccent(coalesce(title, '') || ' ' || coalesce(company, ''))), 'A') ||
        setweight(to_tsvector('simple', f_unaccent(skills::text || ' ' || nice_to_have::text)), 'B') ||
        setweight(to_tsvector('simple', f_unaccent(coalesce(location, '') || ' ' || coalesce(summary, ''))), 'C') ||
        setweight(to_tsvector('simple', f_unaccent(coalesce(raw_text, ''))), 'D')
    ) STORED,
    UNIQUE (user_id, url)
);
CREATE INDEX offers_search_idx ON offers USING gin (search);
CREATE INDEX offers_user_created_idx ON offers (user_id, created_at DESC);

-- My own directories (an offer sits in at most one; none = unfiled)
CREATE TABLE folders (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    name       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX folders_user_name_idx ON folders (user_id, lower(name));

-- What I do with an offer (1:1)
CREATE TABLE applications (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL,
    offer_id       uuid NOT NULL UNIQUE REFERENCES offers (id) ON DELETE CASCADE,
    status         text NOT NULL DEFAULT 'saved',
    next_action    text,
    next_action_at timestamptz,
    applied_at     timestamptz,
    channel        text,
    folder_id      uuid REFERENCES folders (id) ON DELETE SET NULL,
    notes          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX applications_user_idx ON applications (user_id);

-- People to reach for an application (third-party personal data)
CREATE TABLE contacts (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL,
    application_id uuid NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    name           text NOT NULL,
    role           text,
    linkedin_url   text,
    notes          text,
    reached_out    boolean NOT NULL DEFAULT false,
    reached_at     timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX contacts_application_idx ON contacts (application_id);

-- Saved views: a named filter + sort + layout
CREATE TABLE views (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    name       text NOT NULL,
    filters    jsonb NOT NULL DEFAULT '{}',
    layout     text NOT NULL DEFAULT 'grid',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX views_user_name_idx ON views (user_id, lower(name));

-- Append-only history (with who acted: user, ai, automation)
CREATE TABLE events (
    id             bigserial PRIMARY KEY,
    user_id        uuid NOT NULL,
    offer_id       uuid REFERENCES offers (id) ON DELETE SET NULL,
    application_id uuid REFERENCES applications (id) ON DELETE SET NULL,
    actor          text NOT NULL,
    type           text NOT NULL,
    payload        jsonb NOT NULL DEFAULT '{}',
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_user_idx ON events (user_id, created_at DESC);

-- Vectors for meaning-based search (derived: rebuilt when the text or the embedding model changes).
-- No fixed dimension, so the embedding model can change; exact search is fast at this scale.
CREATE TABLE offer_embeddings (
    offer_id   uuid PRIMARY KEY REFERENCES offers (id) ON DELETE CASCADE,
    user_id    uuid NOT NULL,
    model      text NOT NULL,
    text_hash  text NOT NULL,
    embedding  extensions.vector NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Parsed CV profile + the uploaded file, one per user
CREATE TABLE profiles (
    user_id     uuid PRIMARY KEY,
    profile     jsonb NOT NULL,
    source_file text,
    cv_file     bytea,
    cv_mime     text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Every model call (cost, latency, prompt version), per user when known
CREATE TABLE llm_calls (
    id             bigserial PRIMARY KEY,
    user_id        uuid,
    created_at     timestamptz NOT NULL DEFAULT now(),
    role           text NOT NULL,
    provider       text NOT NULL,
    model          text NOT NULL,
    prompt_version text,
    offer_id       uuid,
    status         text NOT NULL,
    http_status    integer,
    input_tokens   integer,
    output_tokens  integer,
    latency_ms     integer,
    cost_usd       numeric,
    error          text,
    request        text,
    response       text
);

-- Defense in depth: even if this schema were exposed through Supabase's REST API, row-level security
-- without policies denies every row to anon/authenticated clients. The API connects as the table owner.
ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE views ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE offer_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY;
