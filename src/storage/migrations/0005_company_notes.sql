-- Several notes per company, each with an optional flag and a pin (replaces the single notes text).

CREATE TABLE company_notes (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
    body       text NOT NULL,
    flag       text CHECK (flag IN ('important', 'follow-up', 'question', 'risk')),
    pinned     boolean NOT NULL DEFAULT false,
    -- clock_timestamp(), not now(): now() is the transaction start, so notes added in one transaction would tie
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX company_notes_company_idx ON company_notes (company_id, pinned DESC, created_at DESC);
ALTER TABLE company_notes ENABLE ROW LEVEL SECURITY;

-- Keep what was already written: each existing notes text becomes the company's first note.
-- (companies.notes stays in place, unused, so nothing is lost if this needs to be undone.)
INSERT INTO company_notes (user_id, company_id, body, created_at, updated_at)
SELECT user_id, id, notes, updated_at, updated_at FROM companies WHERE btrim(notes) <> '';
