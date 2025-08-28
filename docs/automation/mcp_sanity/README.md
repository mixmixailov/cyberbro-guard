# MCP Sanity Check Results

## Overview

Данная директория содержит результаты проверки работоспособности MCP (Model Context Protocol) серверов, необходимых для разработки проекта CyberBro Guard.

## Проверяемые MCP Серверы

### ✅ Context7 MCP
**Статус**: OPERATIONAL  
**Функциональность**: Поиск документации и библиотек  
**Последняя проверка**: 2025-08-27_21-16-21  

**Возможности**:
- Разрешение library ID по названию
- Получение документации библиотек
- Поиск code snippets
- Trust score оценка библиотек

**Результаты тестирования**:
- ✅ Успешное разрешение "telegram-bot-api"
- ✅ Получено 30 релевантных библиотек
- ✅ Высокое качество данных (trust scores, descriptions)
- ✅ Быстрое время отклика (< 2 сек)

### ⚠️ Brave Search MCP
**Статус**: PARTIAL FAILURE  
**Функциональность**: Web поиск и исследование  
**Последняя проверка**: 2025-08-27_21-16-21  

**Обнаруженные проблемы**:
- ❌ HTTP 422 error при deep-search
- ⚠️ Возможны проблемы с API ключом или квотой
- ⚠️ Требует дополнительной настройки

**Рекомендации**:
- Проверить конфигурацию API ключа
- Повторить тест через 24 часа
- Использовать Context7 как альтернативу для документации

### ✅ Playwright MCP
**Статус**: OPERATIONAL  
**Функциональность**: Браузерная автоматизация и E2E тестирование  
**Последняя проверка**: 2025-08-27_21-16-21  

**Возможности**:
- Снапшоты страниц
- Навигация и взаимодействие с элементами
- Скриншоты и запись видео
- Выполнение JavaScript
- Мониторинг сети

**Результаты тестирования**:
- ✅ Успешная инициализация браузера
- ✅ Создание снапшотов страниц
- ✅ Быстрое время отклика (< 1 сек)
- ✅ Готов для E2E тестирования

## Файловая структура

```
docs/automation/mcp_sanity/
├── README.md                           # Этот файл
├── context7_YYYY-MM-DD_HH-mm-ss.txt   # Результаты Context7
├── brave-search_YYYY-MM-DD_HH-mm-ss.txt  # Результаты Brave Search
└── playwright_YYYY-MM-DD_HH-mm-ss.txt    # Результаты Playwright
```

## Автоматизация проверок

### Запуск MCP sanity check
```bash
# Полная проверка всех MCP серверов
make mcp-proof

# Ручной запуск скрипта проверки
./scripts/mcp_sanity_check.sh
```

### Интеграция с CI
MCP проверки включены в `.github/workflows/guard.yml`:

```yaml
- name: MCP Sanity Check
  run: make mcp-proof
```

### Расписание проверок
- **При каждом push**: Быстрая проверка доступности
- **Ежедневно**: Полная функциональная проверка
- **При изменении .cursor/mcp.json**: Полная переконфигурация

## Интерпретация результатов

### ✅ OPERATIONAL
MCP сервер полностью функционален:
- Все тесты прошли успешно
- Быстрое время отклика
- Готов к production использованию

### ⚠️ PARTIAL FAILURE
MCP сервер частично работает:
- Основная функциональность доступна
- Некоторые features недоступны
- Требует внимания, но не блокирует разработку

### ❌ CRITICAL FAILURE
MCP сервер не работает:
- Основная функциональность недоступна
- Требует немедленного исправления
- Может блокировать разработку

## Troubleshooting

### Context7 проблемы
```bash
# Проверка подключения
curl -X POST http://localhost:context7/status

# Перезапуск MCP сервера
# В Cursor IDE: Restart MCP servers
```

### Brave Search проблемы
```bash
# Проверка API ключа
echo $BRAVE_API_KEY

# Тест с альтернативным запросом
# Использование Context7 как fallback
```

### Playwright проблемы
```bash
# Установка браузеров
npx playwright install --with-deps

# Проверка Playwright
npx playwright --version

# Тест базовой функциональности
npx playwright test --headed
```

## Конфигурация MCP

### .cursor/mcp.json
Убедитесь что все MCP серверы правильно настроены:

```json
{
  "mcpServers": {
    "context7": {
      "command": "context7-server",
      "args": ["--port", "8080"]
    },
    "brave-search": {
      "command": "brave-search-server",
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    },
    "playwright": {
      "command": "playwright-server",
      "args": ["--headless"]
    }
  }
}
```

### Environment Variables
```bash
# Для Brave Search
export BRAVE_API_KEY="your-api-key-here"

# Для других MCP серверов (если нужно)
export CONTEXT7_PORT=8080
export PLAYWRIGHT_HEADLESS=true
```

## Мониторинг и Alerts

### Производственный мониторинг
- **Uptime**: Доступность MCP серверов
- **Response time**: Время отклика операций
- **Error rate**: Частота ошибок
- **Usage metrics**: Использование ресурсов

### Автоматические alerts
- Email уведомления при critical failures
- Slack интеграция для team notifications
- GitHub Issues для tracking проблем
- Dashboard для real-time мониторинга

## Best Practices

### Для разработчиков
1. Запускайте `make mcp-proof` перед началом работы
2. Проверяйте MCP статус при необычных ошибках
3. Используйте fallback методы при недоступности MCP
4. Документируйте проблемы в GitHub Issues

### Для CI/CD
1. Включайте MCP проверки в pipeline
2. Fail fast при critical MCP failures
3. Архивируйте результаты проверок
4. Мониторьте тренды доступности

### Для DevOps
1. Регулярно обновляйте MCP серверы
2. Мониторьте API квоты и лимиты
3. Настройте backup/fallback решения
4. Документируйте процедуры восстановления

---

*Последнее обновление*: 2025-08-27  
*Версия*: 1.0  
*Следующая проверка*: Ежедневно автоматически