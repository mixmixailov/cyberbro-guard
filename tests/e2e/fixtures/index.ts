import { test as base, expect } from '@playwright/test';
import { MockTelegramAPI, MockUpdate } from './mock-telegram-api';

// Extend the base test with our custom fixtures
export const test = base.extend<{
  mockTelegramAPI: MockTelegramAPI;
  apiClient: {
    sendUpdate: (update: MockUpdate) => Promise<boolean>;
    getSentMessages: () => any[];
    clearMessages: () => void;
    createTextMessage: (text: string, userId?: number, chatId?: number) => MockUpdate;
    createCallbackQuery: (data: string, userId?: number) => MockUpdate;
    createPreCheckoutQuery: (payload: string, amount?: number, userId?: number) => MockUpdate;
  };
}>({
  // Mock Telegram API fixture
  mockTelegramAPI: async ({}, use) => {
    const mockApi = (global as any).mockTelegramAPI;
    if (!mockApi) {
      throw new Error('Mock Telegram API not available. Check global setup.');
    }
    await use(mockApi);
  },

  // API client helper fixture
  apiClient: async ({ mockTelegramAPI }, use) => {
    const client = {
      sendUpdate: (update: MockUpdate) => mockTelegramAPI.sendUpdate(update),
      getSentMessages: () => mockTelegramAPI.getSentMessages(),
      clearMessages: () => mockTelegramAPI.clearMessages(),
      createTextMessage: (text: string, userId?: number, chatId?: number) => 
        mockTelegramAPI.createTextMessage(text, userId, chatId),
      createCallbackQuery: (data: string, userId?: number) => 
        mockTelegramAPI.createCallbackQuery(data, userId),
      createPreCheckoutQuery: (payload: string, amount?: number, userId?: number) => 
        mockTelegramAPI.createPreCheckoutQuery(payload, amount, userId),
    };

    // Clear messages before each test
    client.clearMessages();
    
    await use(client);
  },
});

export { expect };


