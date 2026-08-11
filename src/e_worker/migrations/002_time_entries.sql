CREATE TABLE IF NOT EXISTS time_entries (
    id               TEXT PRIMARY KEY,
    item_id          TEXT NOT NULL REFERENCES items (id),
    date             TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    note             TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_time_entries_item ON time_entries (item_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_entries (date);
