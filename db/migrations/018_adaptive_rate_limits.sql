-- Create adaptive rate limits configuration table
CREATE TABLE rate_limits (
    scope TEXT PRIMARY KEY,
    rate_limit REAL NOT NULL,
    burst REAL NOT NULL,
    cooldown REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create index for performance
CREATE INDEX idx_rate_limits_updated_at ON rate_limits(updated_at);

-- Insert default rate limit configurations
INSERT OR IGNORE INTO rate_limits (scope, rate_limit, burst, cooldown) VALUES
    ('callback_query', 6.0, 6.0, 15.0),
    ('message', 10.0, 20.0, 30.0),
    ('payment', 5.0, 10.0, 60.0),
    ('admin', 20.0, 50.0, 10.0),
    ('global', 30.0, 100.0, 60.0);


