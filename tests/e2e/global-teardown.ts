import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('[E2E Teardown] Starting global teardown...');

  // Stop mock Telegram API server
  const mockApi = (global as any).mockTelegramAPI;
  if (mockApi) {
    await mockApi.stop();
    console.log('[E2E Teardown] Mock Telegram API stopped');
  }

  console.log('[E2E Teardown] Global teardown completed');
}

export default globalTeardown;


