-- 001: users and tasks
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- trigram indexes make ILIKE '%term%' search fast

CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT        NOT NULL,
    name          TEXT        NOT NULL,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Case-insensitive uniqueness: "Aman@x.com" and "aman@x.com" are the same account.
CREATE UNIQUE INDEX users_email_lower_key ON users (lower(email));

CREATE TABLE tasks (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT        NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    description TEXT        NOT NULL DEFAULT '',
    status      TEXT        NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in_progress', 'done')),
    priority    TEXT        NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high')),
    due_date    DATE,
    -- Order within a board column. Fractional indexing: a card dropped between
    -- positions 1.0 and 2.0 gets 1.5, so a move updates ONE row, not the column.
    position    DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every query is scoped to one user; the board is read per (user, status) in position order.
CREATE INDEX tasks_user_status_position_idx ON tasks (user_id, status, position);
CREATE INDEX tasks_user_due_idx ON tasks (user_id, due_date) WHERE due_date IS NOT NULL;
CREATE INDEX tasks_search_trgm_idx ON tasks USING gin ((title || ' ' || description) gin_trgm_ops);
