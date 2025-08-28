# Rules Compliance Documentation

## Overview

Данный документ описывает систему проверки соответствия проекта CyberBro Guard установленным правилам разработки и архитектурным принципам.

## Automated Compliance Checking

### Скрипт проверки: `scripts/check_rules.sh`

Автоматизированный скрипт для проверки соответствия проекта всем установленным правилам:

```bash
# Запуск полной проверки соответствия
./scripts/check_rules.sh

# Также доступно через Make target
make preflight
```

### Категории проверок

#### 1. Database Guidelines Compliance
**Правило**: `db-guidelines.mdc`

Проверяемые аспекты:
- ✅ Существование директории `app/db/`
- ✅ Наличие файла моделей `app/db/models.py`
- ✅ Директория миграций `db/migrations/`
- ✅ Использование SQLite в коде базы данных
- ✅ Правильная структура инициализации БД

**Критерии прохождения**:
- Все основные файлы и директории БД существуют
- Обнаружено использование SQLite/SQLAlchemy
- Миграции организованы в отдельной директории

#### 2. Handlers Guidelines Compliance
**Правило**: `handlers-guidelines.mdc`

Проверяемые аспекты:
- ✅ Существование директории `app/handlers/`
- ✅ Наличие `__init__.py` для package initialization
- ✅ Паттерн регистрации handlers в коде
- ✅ Модульная структура handlers

**Критерии прохождения**:
- Handlers организованы как Python package
- Обнаружен паттерн регистрации handlers
- Соблюдена модульная архитектура

#### 3. Testing Standards Compliance
**Правило**: `testing-standards.mdc`

Проверяемые аспекты:
- ✅ Существование директории `tests/`
- ✅ Наличие E2E тестов в `tests/e2e/`
- ✅ Конфигурация pytest в `pyproject.toml` или `pytest.ini`
- ✅ Настройка coverage в зависимостях
- ✅ Правильная организация тестовой структуры

**Критерии прохождения**:
- Полная тестовая структура настроена
- E2E тесты присутствуют и настроены
- Coverage и pytest правильно сконфигурированы

#### 4. MCP Requirements Compliance
**Правило**: `mcp-required.mdc`

Проверяемые аспекты:
- ✅ Наличие конфигурации MCP в `.cursor/mcp.json`
- ✅ Настройка Context7 MCP для документации
- ✅ Настройка Brave Search MCP для web поиска
- ✅ Настройка Playwright MCP для E2E тестирования
- ✅ Правильная конфигурация всех required MCPs

**Критерии прохождения**:
- Все необходимые MCPs сконфигурированы
- MCP сервера доступны и функциональны
- Конфигурация соответствует проектным требованиям

#### 5. Project Structure Compliance
**Правило**: `project-always.mdc` и общие стандарты

Проверяемые аспекты:
- ✅ Наличие essential файлов проекта
- ✅ Правильная структура Python package
- ✅ Docker конфигурация присутствует
- ✅ Dependency management настроен
- ✅ Documentation и README актуальны

**Essential Files Checklist**:
- `README.md` - Project documentation
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Development environment
- `app/main.py` - Application entry point
- `app/config.py` - Configuration management
- `pyproject.toml` - Project metadata

#### 6. Security & Dependencies Compliance

Проверяемые аспекты:
- ✅ Конфигурация dependency constraints
- ✅ Environment variables configuration
- ✅ Secrets management правильно настроен
- ✅ Security best practices соблюдены

## Интеграция с CI/CD

### GitHub Actions Integration

Compliance проверки интегрированы в CI pipeline через `.github/workflows/guard.yml`:

```yaml
- name: Rules Compliance Check
  run: |
    chmod +x scripts/check_rules.sh
    ./scripts/check_rules.sh
```

### Make Targets Integration

```bash
# Полная preflight проверка
make preflight

# Запуск только rules compliance
make rules-check

# Полная guard проверка (rules + MCP + tests)
make guard
```

## Exit Codes и Статусы

### Exit Code Meaning
- `0` - Все проверки прошли успешно
- `1` - Критические ошибки обнаружены (FAIL)
- `0` (с warnings) - Прошло с предупреждениями

### Типы результатов

#### ✅ PASS
Проверка прошла успешно. Все требования соблюдены.

#### ❌ FAIL  
Критическая ошибка. Требует исправления перед продолжением.

#### ⚠️ WARN
Предупреждение. Рекомендуется исправить, но не блокирует процесс.

## Troubleshooting Common Issues

### Missing Directory Structures
```bash
# Создание отсутствующих директорий
mkdir -p app/db app/handlers tests/e2e docs/automation
```

### Missing Essential Files
```bash
# Создание базовых конфигурационных файлов
touch requirements.txt requirements-dev.txt
touch app/__init__.py app/db/__init__.py
```

### MCP Configuration Issues
```bash
# Проверка MCP статуса
# Используйте Cursor IDE для проверки MCP подключений
# Обратитесь к docs/automation/mcp_sanity/ для диагностики
```

### Pytest Configuration
```bash
# Добавление pytest конфигурации в pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

## Continuous Compliance

### Pre-commit Integration
Рекомендуется запускать compliance проверки перед каждым commit:

```bash
# Добавление в .git/hooks/pre-commit
#!/bin/bash
make preflight || exit 1
```

### Development Workflow
1. **Before starting work**: `make preflight`
2. **During development**: Follow established rules
3. **Before commit**: `make preflight` + `make test`
4. **Before push**: `make guard` (full compliance + MCP + tests)

### Monitoring и Reporting

#### Compliance Metrics
- **Pass Rate**: Процент успешных проверок
- **Warning Rate**: Процент проверок с предупреждениями  
- **Coverage**: Покрытие правил проверками
- **Resolution Time**: Время исправления issues

#### Compliance Dashboard
Результаты compliance проверок доступны через:
- GitHub Actions logs и artifacts
- Local script execution reports
- CI/CD pipeline status badges

## Rules Maintenance

### Adding New Rules
1. Создание `.mdc` файла в `.cursor/rules/`
2. Добавление проверки в `scripts/check_rules.sh`
3. Обновление документации в `rules_compliance.md`
4. Тестирование новой проверки

### Updating Existing Rules
1. Модификация соответствующего `.mdc` файла
2. Обновление логики проверки в скрипте
3. Регрессионное тестирование всех проверок
4. Обновление документации

### Rule Deprecation
1. Маркировка правила как deprecated
2. Предупреждение в output вместо ошибки
3. Документирование migration path
4. Удаление после grace period

## Best Practices

### Для разработчиков
- Запускайте `make preflight` перед началом работы
- Следите за новыми rules в `.cursor/rules/`
- Исправляйте warnings по мере возможности
- Документируйте отклонения от rules с обоснованием

### Для maintainers
- Регулярно проверяйте актуальность rules
- Обновляйте compliance скрипты при изменении архитектуры
- Мониторьте compliance metrics в CI
- Обеспечивайте быстрое время выполнения проверок

### Для DevOps
- Интегрируйте compliance в CI pipeline
- Настройте alerts на compliance failures
- Архивируйте compliance reports для audit
- Оптимизируйте время выполнения проверок

---

*Последнее обновление*: January 2025  
*Версия документа*: 1.0  
*Следующий review*: Quarterly
