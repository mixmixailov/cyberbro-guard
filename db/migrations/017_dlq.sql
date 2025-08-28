-- Dead Letter Queue table for failed jobs/updates
-- Migration: 017_dlq.sql
-- Purpose: Store failed jobs for later replay and analysis

CREATE TABLE IF NOT EXISTS dlq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,                    -- Original job/update identifier 
    type TEXT NOT NULL,                      -- Job type: update, webhook, scheduled_job, etc
    payload TEXT NOT NULL,                   -- JSON serialized job data
    error TEXT NOT NULL,                     -- Error message/stack trace
    attempts INTEGER NOT NULL DEFAULT 0,     -- Number of retry attempts made
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),  -- When moved to DLQ
    last_attempt_at TEXT,                    -- Last retry attempt timestamp
    replayed_at TEXT,                        -- When successfully replayed (NULL if not replayed)
    metadata TEXT                            -- Additional metadata as JSON
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_dlq_type ON dlq(type);
CREATE INDEX IF NOT EXISTS idx_dlq_created_at ON dlq(created_at);
CREATE INDEX IF NOT EXISTS idx_dlq_job_id ON dlq(job_id);
CREATE INDEX IF NOT EXISTS idx_dlq_replayed_at ON dlq(replayed_at);

-- Index for admin queries (unreplayed items)
CREATE INDEX IF NOT EXISTS idx_dlq_unreplayed ON dlq(type, replayed_at) WHERE replayed_at IS NULL;
