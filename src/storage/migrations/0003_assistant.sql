-- Assistant: one conversation per offer (and one for the profile), its messages, and the actions it proposed.

CREATE TABLE conversations (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL,
    kind       text NOT NULL CHECK (kind IN ('offer', 'profile')),
    offer_id   uuid REFERENCES offers (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind = 'offer') = (offer_id IS NOT NULL))
);
CREATE UNIQUE INDEX conversations_offer_idx ON conversations (user_id, offer_id) WHERE kind = 'offer';
CREATE UNIQUE INDEX conversations_profile_idx ON conversations (user_id) WHERE kind = 'profile';

-- Only what the user sees is stored: their messages, the answers, and confirmed/cancelled action notes
CREATE TABLE messages (
    id              bigserial PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    user_id         uuid NOT NULL,
    role            text NOT NULL CHECK (role IN ('user', 'assistant', 'event')),
    content         text NOT NULL,
    attachments     jsonb NOT NULL DEFAULT '[]',   -- [{id, label}] of documents attached to a user message
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation_idx ON messages (conversation_id, id);

-- Changes the assistant proposed; nothing is applied until the user confirms
CREATE TABLE assistant_actions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    user_id         uuid NOT NULL,
    tool            text NOT NULL,
    args            jsonb NOT NULL,
    summary         text NOT NULL,                 -- what the confirmation card says
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled', 'failed')),
    result          text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    decided_at      timestamptz
);
CREATE INDEX assistant_actions_conversation_idx ON assistant_actions (conversation_id, created_at);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_actions ENABLE ROW LEVEL SECURITY;
