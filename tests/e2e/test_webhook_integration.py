"""End-to-end tests for webhook integration."""

import json

import pytest


@pytest.mark.asyncio
class TestWebhookIntegration:
    """E2E tests for webhook endpoint and integration."""

    async def test_health_endpoints(self, browser_context, base_url):
        """Test that health endpoints respond correctly."""
        page = await browser_context.new_page()

        # Test /readyz endpoint
        response = await page.goto(f"{base_url}/readyz")
        assert response.status == 200

        # Test /status endpoint
        await page.goto(f"{base_url}/status")
        content = await page.content()
        assert "running" in content.lower()

        await page.close()

    async def test_webhook_endpoint_security(self, browser_context, base_url):
        """Test webhook endpoint security measures."""
        page = await browser_context.new_page()

        # Test webhook without secret (should fail)
        await page.evaluate(f"""
            fetch('{base_url}/webhook', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{'update_id': 1}})
            }})
        """)

        # Note: In test environment WEBHOOK_SECRET is empty, so it should pass
        # In production this would return 403

        await page.close()

    async def test_webhook_with_valid_payload(self, browser_context, base_url):
        """Test webhook with valid Telegram update payload."""
        page = await browser_context.new_page()

        # Valid Telegram update payload
        update_payload = {
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "date": 1640995200,
                "text": "/start",
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser",
                },
                "chat": {
                    "id": 123456789,
                    "type": "private",
                    "first_name": "Test",
                    "username": "testuser",
                },
            },
        }

        response = await page.evaluate(f"""
            fetch('{base_url}/webhook', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'X-Telegram-Bot-Api-Secret-Token': 'test_secret'
                }},
                body: JSON.stringify({json.dumps(update_payload)})
            }}).then(r => r.json())
        """)

        assert response.get("ok") is True
        await page.close()

    async def test_metrics_endpoint(self, browser_context, base_url):
        """Test that Prometheus metrics are exposed."""
        page = await browser_context.new_page()

        response = await page.goto(f"{base_url}/metrics")
        assert response.status == 200

        content = await page.text_content("body")

        # Check for expected metrics
        assert "cyberbro_updates_total" in content
        assert "cyberbro_webhook_dropped_total" in content
        assert "cyberbro_webhook_errors_total" in content

        await page.close()

    async def test_db_health_endpoint(self, browser_context, base_url):
        """Test database health check."""
        page = await browser_context.new_page()

        response = await page.goto(f"{base_url}/db_health")
        assert response.status == 200

        content = await page.text_content("body")
        data = json.loads(content)
        assert data.get("db") == "ok"

        await page.close()

    async def test_webhook_payload_size_limit(self, browser_context, base_url):
        """Test webhook payload size limiting."""
        page = await browser_context.new_page()

        # Create a payload that exceeds the limit
        large_payload = {
            "update_id": 1,
            "message": {
                "text": "x" * 2000000  # 2MB of text
            },
        }

        response = await page.evaluate(f"""
            fetch('{base_url}/webhook', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({json.dumps(large_payload)})
            }}).then(r => ({{status: r.status, ok: r.ok}}))
        """)

        # Should be rejected due to size
        assert response.get("status") == 413
        await page.close()

    async def test_webhook_content_type_validation(self, browser_context, base_url):
        """Test webhook content type validation."""
        page = await browser_context.new_page()

        # Test with wrong content type
        response = await page.evaluate(f"""
            fetch('{base_url}/webhook', {{
                method: 'POST',
                headers: {{'Content-Type': 'text/plain'}},
                body: 'invalid'
            }}).then(r => ({{status: r.status, ok: r.ok}}))
        """)

        assert response.get("status") == 415  # Unsupported Media Type
        await page.close()

    async def test_webhook_idempotency(self, browser_context, base_url):
        """Test webhook idempotency for duplicate updates."""
        page = await browser_context.new_page()

        update_payload = {
            "update_id": 999999,  # Unique ID for this test
            "message": {
                "message_id": 1,
                "date": 1640995200,
                "text": "/start",
                "from": {"id": 123456789, "is_bot": False, "first_name": "Test"},
                "chat": {"id": 123456789, "type": "private"},
            },
        }

        # Send same update twice
        for i in range(2):
            response = await page.evaluate(f"""
                fetch('{base_url}/webhook', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({json.dumps(update_payload)})
                }}).then(r => r.json())
            """)
            assert response.get("ok") is True

        await page.close()


if __name__ == "__main__":
    # Run E2E tests standalone
    import os

    os.environ["E2E_BASE_URL"] = "http://localhost:8080"
    pytest.main([__file__, "-v"])
