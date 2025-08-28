-- Track per-chat monthly AI usage (soft quota)
CREATE TABLE IF NOT EXISTS ai_usage (
    chat_id INTEGER NOT NULL,
    period TEXT NOT NULL, -- YYYY-MM
    ai_calls INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, period)
);








