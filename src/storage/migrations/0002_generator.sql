-- AI Generator: per-user writing preferences, and generated documents attached to offers.

-- Personal instructions applied to every generated document (style, language, sign-off...)
CREATE TABLE preferences (
    user_id      uuid PRIMARY KEY,
    instructions text NOT NULL DEFAULT '',
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- One row per version: generating, revising with feedback or editing by hand adds a version, never overwrites
CREATE TABLE documents (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL,
    offer_id       uuid NOT NULL REFERENCES offers (id) ON DELETE CASCADE,
    doc_type       text NOT NULL,                 -- cover-letter | cold-email | interview
    version        integer NOT NULL,
    parent_id      uuid REFERENCES documents (id) ON DELETE SET NULL,  -- the version it was revised from
    content        text NOT NULL,
    feedback       text,                          -- what was asked to produce this version (NULL: first draft)
    settings       jsonb NOT NULL DEFAULT '{}',   -- tone / difficulty and the instructions used
    model          text,
    prompt_version text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (offer_id, doc_type, version)
);
CREATE INDEX documents_user_offer_idx ON documents (user_id, offer_id, doc_type, version DESC);

ALTER TABLE preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
