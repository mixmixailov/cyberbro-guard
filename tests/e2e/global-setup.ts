import { chromium, FullConfig } from '@playwright/test';
import { MockTelegramAPI } from './fixtures/mock-telegram-api';

async function globalSetup(config: FullConfig) {
  console.log('[E2E Setup] Starting global setup...');

  // Start mock Telegram API server
  const mockApi = new MockTelegramAPI(8001);
  await mockApi.start();

  // Store mock API reference in global state
  (global as any).mockTelegramAPI = mockApi;

  // Optionally, warm up the application
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Wait for the application to be ready
  let retries = 30;
  while (retries > 0) {
    try {
      await page.goto('http://localhost:8000/status');
      const response = await page.textContent('body');
      if (response && response.includes('"running"')) {
        console.log('[E2E Setup] Application is ready');
        break;
      }
    } catch (error) {
      console.log(`[E2E Setup] Waiting for application... (${retries} retries left)`);
      await page.waitForTimeout(1000);
      retries--;
    }
  }

  if (retries === 0) {
    throw new Error('Application failed to start within timeout');
  }

  await browser.close();
  console.log('[E2E Setup] Global setup completed');
}

export default globalSetup;


