-- Outreach: your categories, reference messages (the library), and the drafts / sent messages written from them.

CREATE TABLE message_categories (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    name       text NOT NULL,
    position   integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX message_categories_user_name_idx ON message_categories (user_id, lower(name));

-- Reference messages. Editing the text bumps `version` and keeps the previous wording in `history`.
CREATE TABLE message_templates (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL,
    category_id uuid REFERENCES message_categories (id) ON DELETE SET NULL,   -- deleted category: "Uncategorized"
    title       text NOT NULL,
    channel     text NOT NULL DEFAULT 'linkedin-message'
                CHECK (channel IN ('linkedin-note', 'linkedin-message', 'email', 'other')),
    body        text NOT NULL,
    pinned      boolean NOT NULL DEFAULT false,
    version     integer NOT NULL DEFAULT 1,
    history     jsonb NOT NULL DEFAULT '[]',     -- [{"version": 1, "body": "...", "replaced_at": "..."}]
    created_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX message_templates_user_idx ON message_templates (user_id, category_id, pinned DESC, updated_at DESC);

-- What you actually write: a draft until you mark it sent. Links survive deletions as NULL.
CREATE TABLE outreach_messages (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL,
    category_id uuid REFERENCES message_categories (id) ON DELETE SET NULL,
    template_id uuid REFERENCES message_templates (id) ON DELETE SET NULL,
    offer_id    uuid REFERENCES offers (id) ON DELETE SET NULL,
    contact_id  uuid REFERENCES contacts (id) ON DELETE SET NULL,
    channel     text NOT NULL DEFAULT 'linkedin-message'
                CHECK (channel IN ('linkedin-note', 'linkedin-message', 'email', 'other')),
    body        text NOT NULL,
    status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'sent')),
    sent_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX outreach_messages_user_idx ON outreach_messages (user_id, status, updated_at DESC);

ALTER TABLE message_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_messages ENABLE ROW LEVEL SECURITY;
