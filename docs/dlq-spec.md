# Dead Letter Queue v1 - Technical Specification

## Overview

**Feature**: Dead Letter Queue (DLQ) for Failed Jobs and Updates  
**Version**: v1.0  
**Status**: Implementation  
**Target**: Production reliability and failure handling

## Problem Statement

### Current Issues
1. **Lost Failed Updates**: When Telegram updates fail processing, they're simply logged and lost
2. **No Failure Analysis**: No systematic way to analyze patterns in failures
3. **Manual Intervention Required**: Failed jobs require manual investigation and reprocessing
4. **Poor Observability**: Limited visibility into failure rates and types
5. **Data Loss Risk**: Critical operations may be permanently lost on transient failures

### Goals
- **Failure Recovery**: Capture and store failed jobs for later replay
- **Systematic Analysis**: Provide tools for analyzing failure patterns
- **Operational Visibility**: Metrics and monitoring for failure tracking
- **Automated Retry**: Built-in retry logic with configurable attempts
- **Admin Interface**: Easy-to-use commands for DLQ management

## Technical Requirements

### Functional Requirements

#### FR1: Failed Job Storage
- **Database Schema**: Table `dlq` with job data, error details, and metadata
- **Job Types**: Support for `update`, `webhook`, `scheduled_job` types
- **Error Context**: Full error messages, stack traces, and attempt counts
- **Temporal Data**: Creation time, last attempt time, replay time tracking

#### FR2: Worker Integration
- **Retry Logic**: Configurable max attempts (default: 3) with exponential backoff
- **Automatic DLQ**: Move to DLQ after max attempts exceeded
- **Graceful Degradation**: Continue processing other items if DLQ operations fail
- **Structured Logging**: Rich log context for debugging and monitoring

#### FR3: CLI Management Interface
- **Replay Command**: `python -m app.worker dlq:replay --id N`
- **List Command**: `python -m app.worker dlq:list [--type TYPE] [--limit N]`
- **Stats Command**: `python -m app.worker dlq:stats`
- **Cleanup Command**: `python -m app.worker dlq:cleanup --days N`

#### FR4: Admin Commands
- **Telegram Integration**: `/dlq_stats` command for admins
- **Real-time Stats**: Current DLQ size, recent failures, type breakdown
- **Access Control**: Admin-only access with proper authorization

#### FR5: Metrics and Monitoring
- **Size Gauge**: `cyberbro_dlq_size{type}` - current unreplayed items
- **Inflow Counter**: `cyberbro_dlq_in_total{type,reason}` - items added to DLQ
- **Replay Counter**: `cyberbro_dlq_replayed_total{type}` - successful replays

### Technical Specifications

#### Database Schema
```sql
CREATE TABLE dlq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,                    -- Original job identifier
    type TEXT NOT NULL,                      -- Job type: update, webhook, scheduled_job
    payload TEXT NOT NULL,                   -- JSON serialized job data
    error TEXT NOT NULL,                     -- Error message/stack trace
    attempts INTEGER NOT NULL DEFAULT 0,     -- Number of retry attempts made
    created_at TEXT NOT NULL,                -- When moved to DLQ (UTC ISO)
    last_attempt_at TEXT,                    -- Last retry timestamp
    replayed_at TEXT,                        -- Successful replay timestamp
    metadata TEXT                            -- Additional JSON metadata
);

-- Indexes for efficient queries
CREATE INDEX idx_dlq_type ON dlq(type);
CREATE INDEX idx_dlq_created_at ON dlq(created_at);
CREATE INDEX idx_dlq_job_id ON dlq(job_id);
CREATE INDEX idx_dlq_unreplayed ON dlq(type, replayed_at) WHERE replayed_at IS NULL;
```

#### DLQ Service API
```python
class DLQService:
    @staticmethod
    def add_to_dlq(job_id: str, job_type: str, payload: Dict, 
                   error: Exception | str, attempts: int, 
                   metadata: Optional[Dict] = None) -> int

    @staticmethod
    def get_dlq_item(dlq_id: int) -> Optional[DLQItem]
    
    @staticmethod
    def get_dlq_items(job_type: Optional[str] = None, 
                     only_unreplayed: bool = True, 
                     limit: int = 100) -> List[DLQItem]
    
    @staticmethod
    def mark_replayed(dlq_id: int) -> bool
    
    @staticmethod
    def get_stats_by_type() -> Dict[str, Dict[str, int]]
```

#### Worker Integration Flow
```
Update Received
    ↓
[Attempt 1] → Success? → Continue
    ↓ No
[Attempt 2] → Success? → Continue  
    ↓ No
[Attempt 3] → Success? → Continue
    ↓ No
Move to DLQ + Log Error + Update Metrics
```

### Performance Requirements

#### PR1: Latency Impact
- **DLQ Operations**: < 5ms overhead for DLQ insertion
- **Worker Throughput**: No significant impact on normal processing speed
- **Database Performance**: Optimized indexes for common query patterns

#### PR2: Storage Efficiency
- **JSON Compression**: Use TEXT storage for flexibility vs. performance
- **Cleanup Strategy**: Automatic removal of old replayed items (30+ days)
- **Index Optimization**: Selective indexes for unreplayed items only

#### PR3: Reliability Targets
- **DLQ Availability**: 99.9% successful DLQ operations 
- **Data Integrity**: No data loss during DLQ operations
- **Recovery Time**: < 1 minute to replay critical failed updates

## Implementation Details

### Core Components

#### DLQ Database Migration
```sql
-- Migration: 017_dlq.sql
-- Creates dlq table with proper indexes and constraints
```

#### DLQService Class
```python
# app/services/dlq.py
# Handles all DLQ operations with proper error handling and metrics
```

#### Worker Enhancement
```python
# Modified app/main.py _worker() function
# Adds retry loop with exponential backoff and DLQ fallback
```

#### CLI Interface
```python
# app/worker.py
# Command-line tool for DLQ management and replay operations
```

### Error Handling Scenarios

#### Scenario 1: Telegram Update Processing Failure
```
Webhook Update → Parse → Process → Handler Error → Retry → DLQ
```

#### Scenario 2: Scheduled Job Failure
```
Cron Trigger → Job Execute → Database Error → Retry → DLQ
```

#### Scenario 3: Network Timeout
```
API Call → Timeout → Retry with Backoff → Max Attempts → DLQ
```

### Replay Strategies

#### Update Replay
```python
# Reconstruct Telegram Update object from payload
# Re-inject into PTB processing pipeline
# Handle potential duplicate processing issues
```

#### Job Replay
```python
# Execute job function with stored parameters
# Ensure job is idempotent or handle side effects
# Update replay timestamp on success
```

## Validation Matrix

| Scenario | Input | Expected Behavior | Verification |
|----------|-------|-------------------|--------------|
| **Update Failure** | Failed update after 3 attempts | Moved to DLQ with error details | Unit test + integration |
| **Successful Retry** | Update fails attempt 1-2, succeeds 3 | No DLQ entry, success logged | Unit test |
| **DLQ Replay** | CLI replay command with valid ID | Item marked as replayed | CLI test |
| **Admin Stats** | /dlq_stats telegram command | Stats displayed to admin | Integration test |
| **Metrics Update** | DLQ operations | Prometheus metrics incremented | Metrics test |
| **Cleanup Job** | Old replayed items | Items removed from DLQ | Unit test |
| **Concurrent Access** | Multiple workers | No race conditions in DLQ | Load test |
| **Invalid Replay** | Replay non-existent item | Error message, no side effects | Error test |

## Testing Strategy

### Unit Tests
- **DLQ Service**: All CRUD operations and edge cases
- **Helper Functions**: Update and job DLQ addition functions
- **Data Structures**: DLQItem serialization and deserialization
- **Error Handling**: Exception scenarios and fallback behavior

### Integration Tests
- **Worker Integration**: End-to-end failure → DLQ → replay flow
- **CLI Commands**: All worker CLI commands with various parameters
- **Admin Commands**: Telegram admin command functionality
- **Metrics**: Prometheus metrics collection and accuracy

### Performance Tests
- **High Failure Rate**: Stress test with 50% failure rate
- **Large DLQ**: Performance with 10,000+ DLQ items
- **Concurrent Replays**: Multiple simultaneous replay operations
- **Database Load**: DLQ operations under heavy concurrent load

## Migration Plan

### Phase 1: Core Implementation (Current)
- ✅ Database schema migration (017_dlq.sql)
- ✅ DLQ service implementation (app/services/dlq.py)
- ✅ Worker integration with retry logic
- ✅ Basic CLI commands for management

### Phase 2: Admin & Monitoring
- ✅ Telegram admin commands (/dlq_stats)
- ✅ Prometheus metrics integration  
- ⏳ Grafana dashboard for DLQ monitoring
- ⏳ Alerting rules for high failure rates

### Phase 3: Advanced Features
- ⏳ Intelligent replay scheduling (off-peak hours)
- ⏳ Failure pattern analysis and reporting
- ⏳ Automatic escalation for critical failures
- ⏳ Integration with external monitoring systems

## Success Metrics

### Operational Metrics
- **Recovery Rate**: > 95% of DLQ items successfully replayed
- **Mean Time to Recovery**: < 30 minutes for critical failures
- **False Positive Rate**: < 1% items in DLQ that shouldn't be there
- **Admin Usage**: Regular use of DLQ stats and management commands

### Business Impact
- **Data Loss Prevention**: Zero permanent loss of critical updates
- **Operational Efficiency**: 50% reduction in manual failure investigation
- **System Reliability**: 99.9% successful processing including retries
- **Debugging Speed**: 75% faster failure root cause analysis

## Risk Assessment

### Implementation Risks
- **Database Performance**: DLQ table growth impacting query performance - **Mitigation**: Regular cleanup + optimized indexes
- **Memory Usage**: Large payloads in DLQ consuming memory - **Mitigation**: Payload size limits + compression
- **Replay Side Effects**: Non-idempotent operations causing issues - **Mitigation**: Careful replay logic + documentation

### Operational Risks
- **DLQ Overflow**: Too many failures overwhelming DLQ - **Mitigation**: Monitoring + alerting + rate limiting
- **Infinite Loops**: Replay operations failing and re-entering DLQ - **Mitigation**: Replay attempt tracking + circuit breaker
- **Admin Overload**: Too many DLQ alerts fatiguing administrators - **Mitigation**: Intelligent alerting thresholds

## Future Enhancements

### V2 Considerations
- **Intelligent Retry Delays**: ML-based optimal retry timing
- **Failure Classification**: Automatic categorization of error types
- **Bulk Replay Operations**: Replay multiple items with single command
- **DLQ Analytics Dashboard**: Rich visualization of failure patterns
- **Cross-Instance DLQ**: Shared DLQ across multiple bot instances

### Integration Opportunities
- **External Logging**: Forward DLQ events to external log aggregation
- **Incident Management**: Auto-create tickets for high-priority failures
- **Notification Systems**: Real-time alerts via email/Slack/PagerDuty
- **Audit Trail**: Complete audit log of all DLQ operations and replays
