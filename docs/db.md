# Database Layer Documentation

## Overview

CyberBro Guard использует SQLite как основную базу данных с WAL (Write-Ahead Logging) режимом для улучшенной производительности и надёжности в concurrent workloads.

## SQLite Configuration

### Connection Settings

```python
def _get_conn(immediate: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(APP_DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Core SQLite optimizations
    conn.execute("PRAGMA journal_mode=WAL;")      # Write-Ahead Logging
    conn.execute("PRAGMA synchronous=NORMAL;")    # Balanced durability/performance
    conn.execute("PRAGMA foreign_keys=ON;")       # Referential integrity
    conn.execute("PRAGMA busy_timeout=5000;")     # 5s wait for locks
    
    if immediate:
        conn.execute("BEGIN IMMEDIATE;")  # Immediate RESERVED lock
```

### Key Features

#### 1. WAL Mode (Write-Ahead Logging)
- **Concurrent reads** не блокируются writes
- **Better performance** для read-heavy workloads
- **Automatic checkpointing** через SQLite
- **Crash recovery** through WAL replay

#### 2. Foreign Key Constraints
- **Referential integrity** enforcement
- **Cascade operations** поддерживаются
- **Data consistency** автоматически maintained

#### 3. Busy Timeout
- **5 second timeout** для database lock acquisition
- **Automatic retry** при SQLITE_BUSY errors
- **Graceful handling** concurrent access

## Transaction Management

### Regular Transactions

Используются для большинства operations:

```python
# Automatic transaction management
execute("INSERT INTO users (tg_id, created_at) VALUES (?, ?)", (user_id, timestamp))
fetchone("SELECT * FROM users WHERE tg_id = ?", (user_id,))
```

### BEGIN IMMEDIATE Transactions

Для критических operations где важно избежать database locking:

```python
# Critical writes with immediate lock acquisition
execute_immediate("INSERT INTO payments (tg_id, amount_cents) VALUES (?, ?)", (user_id, amount))

# Or using the immediate parameter
execute("UPDATE subscriptions SET until = ? WHERE id = ?", (new_date, sub_id), immediate=True)
```

#### When to Use BEGIN IMMEDIATE

✅ **Use for:**
- **Payment processing** - критический для consistency
- **User subscription updates** - состояние должно быть atomic
- **Balance modifications** - financial operations
- **Critical state changes** - модерация actions
- **High-concurrency operations** - multiple simultaneous requests

❌ **Don't use for:**
- **Read operations** - fetchone/fetchall не нуждаются в locks
- **Bulk inserts** - may hold locks too long
- **Non-critical logs** - performance logs, metrics
- **Temporary data** - cache entries, sessions

### Connection Context Management

Все database operations используют context managers для automatic cleanup:

```python
# Automatic connection closing and transaction handling
with _get_conn() as conn:
    cursor = conn.execute(query, params)
    conn.commit()  # Automatic on success
    # conn.rollback() automatic on exception
```

## Database Schema

### Core Tables

#### Users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,         -- Telegram user ID
    created_at TEXT NOT NULL,              -- ISO timestamp
    lang TEXT,                             -- User language preference
    plan TEXT NOT NULL DEFAULT 'free',    -- Subscription plan
    until TEXT                             -- Plan expiration
);
```

#### Payments
```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,                -- User who paid
    amount_cents INTEGER NOT NULL,         -- Amount in cents/XTR
    currency TEXT NOT NULL,                -- Currency code (XTR)
    provider TEXT,                         -- Payment provider
    status TEXT,                          -- Payment status
    created_at TEXT NOT NULL,             -- Payment timestamp
    raw_json TEXT                         -- Original payment data
);
```

#### Subscriptions
```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,               -- Subscriber
    plan_code TEXT NOT NULL,              -- Plan identifier
    until TEXT,                           -- Expiration date
    created_at TEXT NOT NULL,             -- Subscription start
    FOREIGN KEY(plan_code) REFERENCES plans(code)
);
```

### Indexes

Critical indexes для performance:

```sql
-- User lookups by Telegram ID
CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id);

-- Payment queries by user and status
CREATE INDEX IF NOT EXISTS idx_payments_tg_id ON payments(tg_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- Subscription expiration queries  
CREATE INDEX IF NOT EXISTS idx_subscriptions_until ON subscriptions(until);
CREATE INDEX IF NOT EXISTS idx_subscriptions_tg_id ON subscriptions(tg_id);

-- Idempotency cleanup
CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at ON idempotency(expires_at);
```

## Best Practices

### 1. Connection Management

```python
# ✅ Good: Use context managers
with _get_conn() as conn:
    result = conn.execute(query, params)
    conn.commit()

# ❌ Bad: Manual connection handling
conn = _get_conn()
result = conn.execute(query, params)
conn.close()  # Easy to forget
```

### 2. Parameter Binding

```python
# ✅ Good: Parameterized queries
execute("SELECT * FROM users WHERE tg_id = ?", (user_id,))

# ❌ Bad: String formatting (SQL injection risk)
execute(f"SELECT * FROM users WHERE tg_id = {user_id}")
```

### 3. Transaction Scope

```python
# ✅ Good: Minimal transaction scope
execute_immediate("UPDATE balances SET amount = amount - ? WHERE user_id = ?", (cost, user_id))

# ❌ Bad: Long-running transactions
with _get_conn(immediate=True) as conn:
    # ... lots of work ...
    # Holds RESERVED lock too long
    conn.commit()
```

### 4. Error Handling

```python
# ✅ Good: Specific error handling
try:
    execute_immediate("INSERT INTO payments (...) VALUES (...)", params)
except sqlite3.IntegrityError as e:
    if "UNIQUE constraint failed" in str(e):
        # Handle duplicate payment
        pass
    else:
        raise
```

## Performance Considerations

### Read Performance

- **Use indexes** для frequent queries
- **Limit result sets** с LIMIT clauses
- **Avoid SELECT *** на больших tables
- **Batch multiple reads** когда возможно

### Write Performance

- **Use BEGIN IMMEDIATE** для critical operations
- **Batch multiple inserts** в single transaction
- **Minimize transaction duration**
- **Use appropriate isolation levels**

### Concurrent Access

- **WAL mode** allows concurrent readers
- **BEGIN IMMEDIATE** prevents lock conflicts
- **Busy timeout** handles temporary contention
- **Connection pooling** через _get_conn()

## Monitoring & Maintenance

### Health Checks

```python
# Database connectivity check
async def db_health():
    try:
        await asyncio.to_thread(execute, "SELECT 1")
        return {"db": "ok"}
    except Exception as e:
        return {"db": "error", "details": str(e)}
```

### WAL Checkpoint Management

WAL files растут со временем и require periodic checkpointing:

```python
# Manual checkpoint (for scheduled maintenance)
def wal_checkpoint():
    with _get_conn() as conn:
        result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
        logger.info("WAL checkpoint: %s pages", result[0])
```

**Рекомендация**: Run checkpoint в low-traffic periods (e.g., daily at 4 AM).

### Database Backup

```python
# Create backup copy
def backup_database(backup_path: str):
    import shutil
    with _get_conn() as conn:
        # Ensure WAL is checkpointed
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    
    # Copy database file
    shutil.copy2(APP_DB_PATH, backup_path)
    logger.info("Database backed up to %s", backup_path)
```

## Troubleshooting

### Common Issues

#### 1. Database Locked Errors
```
sqlite3.OperationalError: database is locked
```

**Solutions:**
- Use `execute_immediate()` для critical writes
- Reduce transaction duration
- Check для long-running queries
- Verify busy_timeout configuration

#### 2. WAL Files Growing Large
```
data/app.db-wal becomes > 100MB
```

**Solutions:**
- Run manual checkpoint: `PRAGMA wal_checkpoint(TRUNCATE)`
- Check для stuck readers
- Restart application to force checkpoint
- Monitor WAL size в health checks

#### 3. Foreign Key Violations
```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

**Solutions:**
- Ensure referenced data exists
- Check insertion order (parents before children)
- Verify foreign key constraints are enabled
- Use transactions для multi-table operations

#### 4. Disk Space Issues
```
sqlite3.OperationalError: disk I/O error
```

**Solutions:**
- Monitor disk space usage
- Implement data retention policies
- Archive old data periodically
- Use database vacuum для space reclamation

### Debug Queries

```sql
-- Check WAL status
PRAGMA journal_mode;
PRAGMA wal_autocheckpoint;

-- Monitor database size
.database

-- Check foreign key status
PRAGMA foreign_keys;

-- Analyze query performance
EXPLAIN QUERY PLAN SELECT ...;

-- Check busy timeout setting
PRAGMA busy_timeout;
```

## Migration Strategy

### Forward-Only Migrations

Используем простой forward-only approach:

```sql
-- db/migrations/017_add_feature.sql
-- forward-only: add new feature table
CREATE TABLE IF NOT EXISTS feature_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    feature_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    UNIQUE(chat_id, feature_name)
);

CREATE INDEX IF NOT EXISTS idx_feature_settings_chat_id ON feature_settings(chat_id);
```

### Migration Execution

```python
# Apply pending migrations
from app.utils.migrate import migrate
migrate("db/migrations", dry_run=False)
```

**Important**: Always backup database before applying migrations в production.

## Security Considerations

### SQL Injection Prevention

- **Always use parameterized queries**
- **Never format SQL strings** с user input
- **Validate input types** before database calls
- **Use prepared statements** где возможно

### Access Control

- **Database file permissions**: 600 (read/write owner only)
- **Directory permissions**: 700 (access owner only)
- **No network access**: SQLite is local-only
- **Connection timeouts**: Prevent resource exhaustion

### Data Protection

- **Sensitive data encryption**: Encrypt before storing
- **PII handling**: Minimal storage, proper deletion
- **Audit trails**: Log critical operations
- **Backup encryption**: Encrypt backup files

## Development Workflow

### Local Development

```bash
# Initialize database
python -c "from app.db.session import init_db; init_db()"

# Apply migrations
python -m app.utils.migrate --dir db/migrations

# Check database
sqlite3 data/app.db ".schema"
```

### Testing

```python
# Use temporary database for tests
@pytest.fixture
def temp_db(monkeypatch):
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        monkeypatch.setattr("app.db.session.APP_DB_PATH", Path(f.name))
        init_db()
        yield Path(f.name)
```

### Production Deployment

1. **Backup existing database**
2. **Apply migrations** с dry-run first
3. **Verify schema changes**
4. **Monitor application logs**
5. **Check performance metrics**

## Resources

- [SQLite WAL Mode Documentation](https://www.sqlite.org/wal.html)
- [SQLite Pragma Statements](https://www.sqlite.org/pragma.html)
- [SQLite Concurrency](https://www.sqlite.org/lockingv3.html)
- [Python sqlite3 Module](https://docs.python.org/3/library/sqlite3.html)


