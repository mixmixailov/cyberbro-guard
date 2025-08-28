# Adaptive Rate Limits v1 Specification

## Overview

Данная спецификация описывает требования к системе настраиваемых лимитов скорости (Adaptive Rate Limits) для проекта CyberBro Guard с возможностью изменения конфигурации в runtime.

## Problem Statement

### Текущие проблемы
1. **Статичные rate limits** — невозможно изменить лимиты без перезапуска приложения
2. **Негибкая настройка** — все scope используют одинаковые параметры rate limiting
3. **Отсутствие административного интерфейса** — нет возможности управлять лимитами через Telegram команды
4. **Нет кеширования конфигурации** — каждый запрос требует обращения к базе данных
5. **Отсутствие мониторинга** — нет возможности просмотреть текущие настройки и статистику

### Бизнес-импакт
- **Время реакции на атаки увеличивается** — для изменения лимитов нужен перезапуск
- **Негибкость в управлении нагрузкой** — невозможно адаптировать лимиты под изменяющиеся условия
- **Повышенная нагрузка на БД** — отсутствие кеширования создает дополнительные запросы
- **Сложность администрирования** — требуется доступ к серверу для изменения конфигурации

## Goals

### Основные цели
1. **Runtime конфигурация**
   - Возможность изменения rate limits без перезапуска приложения
   - Немедленное применение новых настроек
   - Сохранение конфигурации в базе данных

2. **Административный интерфейс**
   - Telegram команды для управления rate limits
   - Просмотр текущих конфигураций и статистики
   - Безопасность доступа только для администраторов

3. **Производительность и кеширование**
   - In-memory кеширование с TTL=30s
   - Минимизация обращений к базе данных
   - Автоматическая инвалидация кеша при изменениях

4. **Гибкость настройки**
   - Индивидуальные настройки для разных scope (callback_query, message, payment, admin, global)
   - Настраиваемые параметры: rate, burst, cooldown
   - Автоматическая загрузка дефолтных значений

5. **Мониторинг и наблюдаемость**
   - Статистика использования кеша
   - Логирование изменений конфигурации
   - Команды для просмотра состояния системы

## Requirements

### Functional Requirements

#### FR-1: Database Schema
- **Описание**: Таблица rate_limits для хранения конфигурации лимитов
- **Критерии приёмки**:
  - Поля: scope (PK), rate_limit, burst, cooldown, updated_at
  - Индекс по updated_at для оптимизации запросов
  - Поддержка UPSERT операций для обновления конфигурации

#### FR-2: Rate Limit Service
- **Описание**: Сервис AdaptiveRateLimitService с кешированием
- **Критерии приёмки**:
  - In-memory кеш с TTL=30 секунд
  - Методы для CRUD операций с конфигурацией
  - Автоматическая инвалидация кеша при обновлениях
  - Thread-safe операции с использованием asyncio.Lock

#### FR-3: Middleware Integration
- **Описание**: Интеграция с существующим middleware для rate limiting
- **Критерии приёмки**:
  - Чтение конфигурации из кеша вместо статичных значений
  - Создание token buckets на основе конфигурации
  - Fail-open поведение при ошибках (разрешать запросы)

#### FR-4: Admin Commands
- **Описание**: Telegram команды для управления rate limits
- **Критерии приёмки**:
  - `/ratelimit set <scope> <limit> <burst> <cooldown>` - установка лимитов
  - `/ratelimit list` - просмотр всех конфигураций
  - `/ratelimit status` - статистика сервиса и кеша
  - `/ratelimit delete <scope>` - удаление конфигурации
  - Доступ только для администраторов с проверкой is_admin()

#### FR-5: Default Configuration
- **Описание**: Автоматическая загрузка дефолтных значений
- **Критерии приёмки**:
  - При старте приложения проверяется наличие конфигурации
  - Если таблица пуста, загружаются дефолтные значения для всех scope
  - Дефолтные scope: callback_query, message, payment, admin, global

### Non-Functional Requirements

#### NFR-1: Performance
- **Cache TTL**: 30 секунд для balance между производительностью и свежестью данных
- **Database operations**: Минимизация запросов через эффективное кеширование
- **Response time**: < 1ms для получения конфигурации из кеша

#### NFR-2: Reliability
- **Fail-open behavior**: При ошибках разрешать запросы вместо блокировки
- **Graceful degradation**: Система работает даже при проблемах с БД
- **Atomic operations**: Обновления конфигурации выполняются атомарно

#### NFR-3: Security
- **Admin-only access**: Все команды управления доступны только администраторам
- **Input validation**: Валидация всех параметров rate limits
- **Audit logging**: Логирование всех изменений конфигурации

## Technical Specifications

### Database Schema
```sql
CREATE TABLE rate_limits (
    scope TEXT PRIMARY KEY,
    rate_limit REAL NOT NULL,
    burst REAL NOT NULL,
    cooldown REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rate_limits_updated_at ON rate_limits(updated_at);
```

### Default Configurations
```python
DEFAULT_CONFIGS = {
    'callback_query': (6.0, 6.0, 15.0),    # rate, burst, cooldown
    'message': (10.0, 20.0, 30.0),
    'payment': (5.0, 10.0, 60.0),
    'admin': (20.0, 50.0, 10.0),
    'global': (30.0, 100.0, 60.0),
}
```

### Cache Configuration
- **TTL**: 30 seconds
- **Storage**: In-memory dictionary with timestamps
- **Invalidation**: Explicit invalidation on configuration updates
- **Concurrency**: Protected by asyncio.Lock for thread safety

### API Interface
```python
# Service methods
async def get_rate_limit_config(scope: str) -> Optional[RateLimitConfig]
async def set_rate_limit_config(scope: str, rate: float, burst: float, cooldown: float) -> RateLimitConfig
async def list_all_configs() -> Dict[str, RateLimitConfig]
async def delete_config(scope: str) -> bool
async def get_cache_stats() -> Dict[str, any]

# Middleware integration
async def get_token_bucket(scope: str) -> Optional[TokenBucket]
async def check_rate_limit(scope: str, user_id: int, chat_id: int) -> bool
```

### Command Interface
```bash
# Set rate limit
/ratelimit set callback_query 6.0 6.0 15.0

# List all configurations
/ratelimit list

# Show service status
/ratelimit status

# Delete configuration
/ratelimit delete custom_scope
```

## Success Criteria

### Definition of Done
1. ✅ Database schema создана с правильными полями и индексами
2. ✅ AdaptiveRateLimitService реализован с кешированием TTL=30s
3. ✅ Middleware интегрирован для чтения из кеша
4. ✅ Команда `/ratelimit set <scope> <limit> <burst> <cooldown>` работает
5. ✅ Дефолтные значения загружаются при старте если таблица пуста
6. ✅ Тесты подтверждают изменение настроек без перезапуска
7. ✅ Документация сгенерирована и обновлена

### Key Performance Indicators
- **Cache hit rate** ≥ 95% для repeated requests
- **Configuration update time** ≤ 100ms для применения изменений
- **Command response time** ≤ 2 seconds для Telegram команд
- **Memory usage** ≤ 1MB для кеша конфигурации

## Dependencies

### Internal Dependencies
- **Database layer**: app.db.session для выполнения SQL запросов
- **Token bucket**: app.services.rate_limit.TokenBucket для rate limiting логики
- **Admin utilities**: app.utils.admin.is_admin для проверки прав доступа
- **Logging**: app.logging_conf для consistent logging

### External Dependencies
- **SQLite**: Хранение конфигурации rate limits
- **asyncio**: Для асинхронных операций и locks
- **python-telegram-bot**: Для обработки команд администратора

## Testing Strategy

### Unit Tests
- **Service layer**: Тестирование всех методов AdaptiveRateLimitService
- **Caching logic**: Проверка TTL, invalidation, concurrent access
- **Validation**: Тестирование валидации параметров rate limits
- **Error handling**: Graceful degradation при ошибках БД

### Integration Tests
- **Database operations**: CRUD операции с реальной БД
- **Middleware integration**: Проверка работы с token buckets
- **Command handlers**: Тестирование Telegram команд
- **Cache behavior**: Проверка поведения кеша в реальных сценариях

### Runtime Tests
- **Configuration changes**: Изменение настроек без перезапуска
- **Cache invalidation**: Применение новых настроек через кеш
- **Performance**: Нагрузочное тестирование кеша и БД
- **Concurrent access**: Проверка thread safety

## Risks and Mitigations

### Risk: Cache Inconsistency
- **Вероятность**: Medium
- **Импакт**: Medium (временно неактуальные лимиты)
- **Mitigation**: Short TTL (30s), explicit invalidation on updates

### Risk: Database Lock Contention
- **Вероятность**: Low
- **Импакт**: Medium (замедление обновлений)
- **Mitigation**: Efficient caching, minimal database writes

### Risk: Configuration Validation Errors
- **Вероятность**: High
- **Импакт**: Low (отклонение неверных команд)
- **Mitigation**: Comprehensive input validation, clear error messages

### Risk: Memory Leak in Cache
- **Вероятность**: Low
- **Импакт**: High (degraded performance over time)
- **Mitigation**: Bounded cache size, periodic cleanup, monitoring

## Future Enhancements

### Phase 2 Features
1. **Per-user rate limiting** — индивидуальные лимиты для пользователей
2. **Dynamic scaling** — автоматическая корректировка лимитов на основе нагрузки
3. **Rate limit policies** — предустановленные конфигурации для разных сценариев
4. **Metrics integration** — экспорт метрик rate limiting в Prometheus

### Advanced Features
1. **Distributed rate limiting** — синхронизация между несколькими инстансами
2. **Machine learning** — автоматическое определение оптимальных лимитов
3. **Geographical rate limiting** — разные лимиты для разных регионов
4. **Time-based rate limiting** — различные лимиты в зависимости от времени

## Implementation Phases

### Phase 1: Core Implementation (Current)
- ✅ Database schema and migrations
- ✅ AdaptiveRateLimitService with caching
- ✅ Middleware integration
- ✅ Basic admin commands
- ✅ Default configuration loading
- ✅ Unit and integration tests

### Phase 2: Enhanced Features
- [ ] Advanced monitoring and metrics
- [ ] Rate limit policies and templates
- [ ] Enhanced admin interface with web UI
- [ ] Performance optimizations

### Phase 3: Enterprise Features
- [ ] Multi-tenant rate limiting
- [ ] Advanced analytics and reporting
- [ ] Machine learning-based optimization
- [ ] High availability and clustering

