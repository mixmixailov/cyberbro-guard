# Jitter Backoff v1 - Technical Specification

## Overview

**Feature**: Jittered Exponential Backoff for Outbound Telegram API Calls  
**Version**: v1.0  
**Status**: Implementation  
**Target**: Production resilience and rate limit compliance

## Problem Statement

### Current Issues
1. **Basic Backoff**: Current implementation uses simple exponential backoff without jitter
2. **Thundering Herd**: Multiple bots/processes hitting rate limits simultaneously 
3. **Poor 429 Handling**: RetryAfter values not properly respected with variation
4. **Limited Observability**: No metrics on retry patterns and backoff effectiveness
5. **Network Fragility**: Network errors cause predictable retry storms

### Goals
- **Reduce API pressure** through intelligent backoff strategies
- **Prevent thundering herd** effects with proper jitter implementation  
- **Improve reliability** for high-volume production deployments
- **Enhanced observability** with structured logging and metrics
- **Configurable behavior** for different deployment scenarios

## Technical Requirements

### Functional Requirements

#### FR1: Jittered Exponential Backoff
- **Decorrelated Jitter**: Blend of previous delay and exponential backoff
- **Full Jitter**: Random delay between 0 and calculated exponential backoff
- **Configuration**: Base delay, maximum delay, jitter type selection

#### FR2: Enhanced RetryAfter Handling  
- **Respect RetryAfter**: Use Telegram's suggested delay when provided
- **Add Jitter**: Apply ±30% jitter to RetryAfter values to prevent synchronization
- **Fallback**: Use exponential backoff when RetryAfter is None/invalid

#### FR3: Structured Logging
- **Log Fields**: `attempt`, `wait_ms`, `reason`, `chat_id`, `method`
- **Log Levels**: INFO for rate limits, WARNING for network errors, ERROR for failures
- **Correlation**: Link retry attempts to original operation context

#### FR4: Metrics and Observability
- **Retry Counter**: `cyberbro_retry_total{reason}` - track retry reasons
- **Backoff Histogram**: `cyberbro_backoff_seconds` - measure actual delays  
- **Reasons**: `rate_limit`, `network_error`, `max_attempts_exceeded`

### Technical Specifications

#### Configuration Schema
```python
class Settings:
    BACKOFF_BASE: float = 0.5     # Base delay in seconds
    BACKOFF_MAX: float = 20.0     # Maximum delay in seconds  
    BACKOFF_JITTER: str = "full"  # Jitter type: full|decorrelated|none
```

#### Jitter Algorithms

**Full Jitter**:
```python
delay = random.uniform(0, min(base * (2 ** attempt), max_delay))
```

**Decorrelated Jitter**:
```python
if attempt == 1:
    delay = random.uniform(0, base)
else:
    exp_backoff = min(base * (2 ** attempt), max_delay)
    delay = random.uniform(base, exp_backoff * 3)
```

**RetryAfter Jitter**:
```python
jitter_range = retry_after * 0.3
delay = retry_after + random.uniform(-jitter_range, jitter_range)
```

#### Error Handling Flow

```
API Call
    ↓
[RetryAfter] → Calculate jittered delay (±30%)
    ↓
[NetworkError] → Exponential backoff with jitter  
    ↓
[Attempt > 5] → Raise exception with metrics
    ↓
[Success] → Update rate limit trackers
```

### Performance Requirements

#### PR1: Latency Impact
- **Overhead**: < 1ms additional latency for backoff calculations
- **Memory**: < 100KB additional memory per SendQueue instance
- **CPU**: Negligible impact on message throughput

#### PR2: Throughput Preservation  
- **Rate Limits**: Maintain existing ~30 msg/s global and ~1 msg/s per-chat limits
- **Queue Size**: Support existing 2000 message queue capacity
- **Concurrency**: No impact on async operation parallelism

#### PR3: Reliability Targets
- **Success Rate**: > 99.5% successful delivery after retries
- **Recovery Time**: < 30s recovery from rate limit episodes  
- **Jitter Effectiveness**: < 10% overlap in retry timing across instances

## Implementation Details

### Core Components

#### SendQueue Enhancement
```python
class SendQueue:
    def _calculate_jittered_backoff(self, attempt: int, base_delay: float | None = None) -> float:
        """Calculate jittered exponential backoff delay."""
        # Implementation handles both RetryAfter and exponential scenarios
        
    async def _send(self, item: _Item) -> None:
        """Enhanced send with comprehensive retry logic."""
        # Rate limiting + retry loop with metrics and logging
```

#### Metrics Integration
```python
# New metrics in app/metrics.py
retry_total = Counter("cyberbro_retry_total", labelnames=("reason",))
backoff_seconds = Histogram("cyberbro_backoff_seconds", buckets=(...))
```

#### Configuration Integration
```python
# Enhanced app/config.py  
BACKOFF_BASE: float = 0.5
BACKOFF_MAX: float = 20.0
BACKOFF_JITTER: str = "full"
```

### Error Scenarios

#### Scenario 1: Telegram Rate Limit (429)
```
Request → 429 RetryAfter(3.0) → Jitter: 2.1-3.9s → Log + Metric → Retry
```

#### Scenario 2: Network Timeout
```  
Request → TimedOut → Exp Backoff: 0.3s (attempt 1) → Log + Metric → Retry
Request → TimedOut → Exp Backoff: 1.2s (attempt 2) → Log + Metric → Retry  
Request → Success → Update trackers
```

#### Scenario 3: Persistent Failure
```
5x TimedOut → Exp Backoff → Final attempt fails → Exception + Metric
```

## Validation Matrix

| Scenario | Input | Expected Behavior | Verification |
|----------|-------|-------------------|--------------|
| **Rate Limit** | 429, retry_after=3 | Delay 2.1-3.9s | Unit test range check |
| **No RetryAfter** | 429, retry_after=None | Use base+jitter | Unit test fallback |
| **Network Error** | TimedOut, attempt=1 | Delay 0-0.5s | Unit test jitter |
| **High Attempt** | TimedOut, attempt=10 | Delay ≤ 20s | Property test bounds |
| **Max Exceeded** | 6 failures | Exception + metric | Integration test |
| **Jitter Variation** | 100 samples | >50 unique values | Property test |
| **Config None** | JITTER=none | Deterministic delays | Unit test no jitter |
| **Config Decorr** | JITTER=decorrelated | Blended delays | Unit test algorithm |

## Testing Strategy

### Unit Tests
- **Jitter Range Validation**: RetryAfter ±30% bounds checking
- **Exponential Bounds**: Backoff never exceeds BACKOFF_MAX
- **Metrics Integration**: Counter/histogram updates on retry events
- **Log Structured Data**: Verify attempt/wait_ms/reason fields
- **Configuration Variants**: Test all jitter types and edge cases

### Property-Based Tests
- **Invariant**: `0 ≤ delay ≤ BACKOFF_MAX` for all attempts
- **Monotonicity**: Later attempts generally have higher expected delays  
- **Jitter Effectiveness**: Sufficient variation in delay calculations
- **Configuration Robustness**: Any valid config produces valid delays

### Integration Tests
- **End-to-End Flow**: Real retry scenarios with mocked bot API
- **Metrics Collection**: Verify Prometheus metrics during retry storms
- **Logging Output**: Structured log validation in realistic scenarios
- **Performance Impact**: Throughput measurement with backoff enabled

## Migration Plan

### Phase 1: Implementation (Current)
- ✅ Add backoff configuration to Settings
- ✅ Implement jitter calculation algorithms  
- ✅ Add retry metrics and logging
- ✅ Enhanced SendQueue._send() method

### Phase 2: Testing
- ✅ Comprehensive unit test suite
- ✅ Property-based test coverage
- ⏳ Integration test scenarios
- ⏳ Performance benchmarking

### Phase 3: Deployment
- ⏳ Staging environment validation
- ⏳ Production rollout with monitoring
- ⏳ Metrics dashboard setup
- ⏳ Performance tuning based on real traffic

## Success Metrics

### Operational Metrics
- **Retry Rate**: < 5% of total API calls require retry
- **429 Recovery**: Average 3-8s delay for rate limit recovery
- **Network Resilience**: > 99% success rate after retries
- **Jitter Distribution**: Uniform spread in retry timing

### Business Impact  
- **Uptime**: No message delivery outages due to rate limits
- **User Experience**: < 10s delay for critical notifications
- **Cost**: No additional API quota consumption
- **Scalability**: Support 10x message volume with same reliability

## Risk Assessment

### Implementation Risks
- **Breaking Changes**: Enhanced error handling might change behavior - **Mitigation**: Comprehensive testing
- **Performance Impact**: Additional calculations per message - **Mitigation**: Micro-benchmarking
- **Configuration Errors**: Invalid jitter settings - **Mitigation**: Validation and defaults

### Operational Risks  
- **Over-Backoff**: Too aggressive delays impact user experience - **Mitigation**: Tunable configuration
- **Under-Backoff**: Insufficient jitter still causes thundering herd - **Mitigation**: Property-based testing
- **Monitoring Gaps**: Missing retry pattern visibility - **Mitigation**: Rich metrics and dashboards

## Future Enhancements

### V2 Considerations
- **Adaptive Backoff**: Learn optimal delays from historical patterns
- **Circuit Breaker**: Temporarily stop retries during extended outages  
- **Priority Queues**: Different backoff strategies for urgent vs. bulk messages
- **Cross-Instance Coordination**: Shared backoff state for multi-pod deployments
