-- Company directory: what you know about each company, useful links, and your to-dos for it.
-- Offers are linked by company name (case-insensitive), so nothing changes in the offers table.

CREATE TABLE companies (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    name       text NOT NULL,
    website    text,
    links      jsonb NOT NULL DEFAULT '[]',     -- [{"label": "...", "url": "https://..."}]
    notes      text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX companies_user_name_idx ON companies (user_id, lower(name));

CREATE TABLE company_todos (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
    text       text NOT NULL,
    done       boolean NOT NULL DEFAULT false,
    due_date   date,
    created_at timestamptz NOT NULL DEFAULT now(),
    done_at    timestamptz
);
CREATE INDEX company_todos_company_idx ON company_todos (company_id, done, created_at);

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_todos ENABLE ROW LEVEL SECURITY;
