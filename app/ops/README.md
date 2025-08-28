# 🛠️ Operations CLI Tools

CLI tools for managing queues, DLQ, and other operational tasks in CyberBro Guard.

## 📋 Queue Management

### Commands

#### `stats` - Queue Statistics
```bash
# Show comprehensive queue and DLQ statistics
python -m app.ops.queue stats
```

**Output:**
- DLQ overview (total, unreplayed, replayed items)
- DLQ items by type with counts and timestamps
- Common error categories from recent items
- Send queue configuration

#### `dlq:list` - List DLQ Items
```bash
# List recent DLQ items (unreplayed only by default)
python -m app.ops.queue dlq:list

# List all DLQ items including replayed
python -m app.ops.queue dlq:list --all

# Filter by job type
python -m app.ops.queue dlq:list --type update
python -m app.ops.queue dlq:list --type scheduled_job

# Limit number of items
python -m app.ops.queue dlq:list --limit 20
```

**Output:**
- Table with ID, Type, Job ID, Error summary, Attempts, Created time, Status
- Quick commands for replay and details

#### `dlq:details` - Show DLQ Item Details
```bash
# Show detailed information for specific DLQ item
python -m app.ops.queue dlq:details --id 123
```

**Output:**
- Basic information (ID, Job ID, Type, Attempts, timestamps)
- Full error details with stack trace
- JSON-formatted payload data
- Metadata information
- Replay command suggestion

#### `dlq:replay` - Replay DLQ Item
```bash
# Replay a specific DLQ item (with confirmation)
python -m app.ops.queue dlq:replay --id 123

# Force replay without confirmation
python -m app.ops.queue dlq:replay --id 123 --force
```

**Behavior:**
- Shows item summary before replay
- Asks for confirmation unless `--force` is used
- Marks item as replayed with timestamp
- Prevents duplicate replay unless `--force` is used

## 🎯 Usage Examples

### Daily Operations Workflow

```bash
# 1. Check overall queue health
python -m app.ops.queue stats

# 2. List recent failures
python -m app.ops.queue dlq:list

# 3. Investigate specific failure
python -m app.ops.queue dlq:details --id 42

# 4. Replay after fixing issue
python -m app.ops.queue dlq:replay --id 42
```

### Monitoring Script

```bash
#!/bin/bash
# check_dlq.sh - Monitor DLQ for critical items

echo "🔍 Checking DLQ status..."
python -m app.ops.queue stats | grep "Unreplayed"

echo "📋 Recent failures:"
python -m app.ops.queue dlq:list --limit 5
```

### Bulk Operations

```bash
# Find all NetworkError items
python -m app.ops.queue dlq:list --type update | grep NetworkError

# List older items for cleanup analysis
python -m app.ops.queue dlq:list --all --limit 100
```

## 📊 Understanding Output

### Queue Statistics

```
📊 Queue Statistics
==================================================

🗃️ Dead Letter Queue Overview:
  Total DLQ Items: 15
  Unreplayed: 3
  Replayed: 12
  Oldest Item: 2024-01-15 10:00:00 UTC
  Newest Item: 2024-01-15 15:30:00 UTC

📋 DLQ Items by Type:
Type            Total    Unreplayed   Replayed   Oldest               Newest
-------------------------------------------------------------------------------------
update          10       2            8          2024-01-15 10:00:00  2024-01-15 15:30:00
scheduled_job   5        1            4          2024-01-15 11:00:00  2024-01-15 14:00:00

⚠️ Common Error Categories (Last 100 items):
  NetworkError    8     (53.3%)
  RetryAfter      4     (26.7%)
  ValueError      2     (13.3%)
  Other           1     (6.7%)

📤 Send Queue Configuration:
  Type: in_memory_asyncio_queue
  Max Size: 2000
  Global Rate: 30 messages/second
  Per Chat Rate: 1 message/second
  Max Retries: 5

  Note: Send queue is in-memory. Check /metrics for real-time stats.
```

### DLQ Item List

```
📋 DLQ Items (unreplayed only)
================================================================================
ID    Type         Job ID             Error                               Attempts Created      Status
---------------------------------------------------------------------------------------------------------
5     update       update_67890       RetryAfter: Rate limited for 30s    1        15:30:15     ❌ Failed
3     update       update_12345       NetworkError: Connection timeout    3        14:20:10     ❌ Failed
1     scheduled    job_payment_check  ValueError: Invalid payment ID      2        10:15:05     ❌ Failed

Showing 3 items (max 50)

💡 To replay an item: python -m app.ops.queue dlq:replay --id 5
💡 To see details: python -m app.ops.queue dlq:details --id 5
```

### DLQ Item Details

```
🔍 DLQ Item Details (ID: 5)
==================================================

ℹ️ Basic Information:
  ID: 5
  Job ID: update_67890
  Type: update
  Attempts: 1
  Created: 2024-01-15 15:30:15 UTC
  Last Attempt: Never
  Replayed: No

❌ Error Details:
----------------------------------------
RetryAfter: Rate limited for 30 seconds
  at send_message (telegram/bot.py:123)
  at handle_message (handlers/basic.py:45)
  ...

📦 Payload:
----------------------------------------
{
  "update_id": 67890,
  "message": {
    "message_id": 123,
    "from": {
      "id": 456,
      "username": "testuser"
    },
    "chat": {
      "id": 789,
      "type": "private"
    },
    "text": "Hello bot!"
  }
}

📋 Metadata:
----------------------------------------
{
  "chat_id": 789,
  "user_id": 456,
  "handler": "message_handler"
}

💡 To replay this item: python -m app.ops.queue dlq:replay --id 5
```

## 🔧 Technical Details

### SQL Helpers

The CLI uses SQL helpers from `app.db.ops.py`:

- `get_queue_stats()` - Comprehensive statistics
- `get_dlq_items_with_details()` - Filtered item retrieval
- `get_dlq_item_by_id()` - Single item details
- `get_operational_summary()` - High-level overview

### Database Tables

**DLQ Table Structure:**
```sql
CREATE TABLE dlq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,          -- JSON
    error TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    last_attempt_at TEXT,
    replayed_at TEXT,              -- NULL if not replayed
    metadata TEXT                  -- JSON
);
```

### Error Categories

The CLI automatically categorizes errors:
- `NetworkError` - Connection issues
- `RetryAfter` - Rate limiting
- `TimedOut` - Timeout errors
- `BadRequest` - Invalid requests
- `Forbidden` - Permission errors
- `ValueError` - Data validation errors
- `KeyError` - Missing data errors
- `Other` - Uncategorized errors

## 🚨 Troubleshooting

### Common Issues

**"No DLQ items found"**
- Normal when system is healthy
- Check that DLQ table exists and is accessible

**"Error getting queue stats"**
- Verify database connectivity
- Check that user has read permissions
- Ensure DLQ table schema is correct

**"Failed to mark item as replayed"**
- Item may already be replayed
- Check that user has write permissions
- Verify item ID exists

### Performance Notes

- `dlq:list` sorts by creation time (newest first)
- Large payloads are automatically formatted with JSON pretty-printing
- Queries use indexes for efficient filtering
- Error summaries are truncated for table display

### Permissions

The CLI requires:
- Read access to DLQ table for `stats`, `dlq:list`, `dlq:details`
- Write access to DLQ table for `dlq:replay`
- Database connection permissions

## 🔗 Integration

### With Monitoring

```bash
# Add to monitoring script
UNREPLAYED=$(python -m app.ops.queue stats | grep "Unreplayed:" | awk '{print $2}')
if [ "$UNREPLAYED" -gt 10 ]; then
    echo "ALERT: $UNREPLAYED unreplayed DLQ items"
fi
```

### With CI/CD

```yaml
# In deployment pipeline
- name: Check DLQ Health
  run: |
    python -m app.ops.queue stats
    UNREPLAYED=$(python -m app.ops.queue dlq:list | wc -l)
    if [ "$UNREPLAYED" -gt 5 ]; then
      echo "⚠️ Warning: $UNREPLAYED unreplayed items in DLQ"
    fi
```

### With Alerting

```bash
# Cron job for alerting
*/15 * * * * cd /app && python -m app.ops.queue stats | grep -q "Unreplayed: [1-9]" && curl -X POST webhook-url
```
