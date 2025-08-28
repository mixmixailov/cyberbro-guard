"""Pytest configuration for E2E tests."""

import pytest
import asyncio
import os
from playwright.async_api import async_playwright


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the application under test."""
    return os.getenv("E2E_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
async def browser():
    """Create a browser instance for the test session."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        yield browser
        await browser.close()


@pytest.fixture(scope="function")
async def page(browser):
    """Create a new page for each test."""
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True
    )
    page = await context.new_page()
    yield page
    await context.close()


@pytest.fixture(scope="session")
def test_update_payload():
    """Sample Telegram update payload for testing."""
    return {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "date": 1640995200,
            "text": "/start",
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 123456789,
                "type": "private",
                "first_name": "Test",
                "username": "testuser"
            }
        }
    }



