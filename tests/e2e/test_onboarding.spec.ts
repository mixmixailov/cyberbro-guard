import { test, expect } from './fixtures';

test.describe('Onboarding Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
  });

  test('should complete onboarding: /start -> i18n buttons -> help', async ({ 
    page, 
    apiClient 
  }) => {
    // Step 1: Send /start command
    const startUpdate = apiClient.createTextMessage('/start', 12345, 12345);
    await apiClient.sendUpdate(startUpdate);

    // Wait for the bot to process the update
    await page.waitForTimeout(1000);

    // Check that bot sent a welcome message
    const messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThan(0);
    
    const welcomeMessage = messages.find(msg => 
      msg.text && msg.text.includes('welcome') || 
      msg.text && msg.text.includes('Welcome') ||
      msg.text && msg.text.includes('Hello')
    );
    expect(welcomeMessage).toBeTruthy();

    // Step 2: Test i18n language selection
    // Simulate clicking on language button (e.g., "🇺🇸 English")
    const langUpdate = apiClient.createCallbackQuery('lang:en', 12345);
    await apiClient.sendUpdate(langUpdate);

    await page.waitForTimeout(500);

    // Check that bot acknowledged language selection
    const updatedMessages = apiClient.getSentMessages();
    expect(updatedMessages.length).toBeGreaterThan(messages.length);

    // Step 3: Request help
    const helpUpdate = apiClient.createTextMessage('/help', 12345, 12345);
    await apiClient.sendUpdate(helpUpdate);

    await page.waitForTimeout(500);

    // Check that bot sent help information
    const helpMessages = apiClient.getSentMessages();
    const helpMessage = helpMessages.find(msg => 
      msg.text && (
        msg.text.includes('help') || 
        msg.text.includes('Help') ||
        msg.text.includes('commands') ||
        msg.text.includes('Commands')
      )
    );
    expect(helpMessage).toBeTruthy();

    // Verify that onboarding flow completed successfully
    expect(helpMessages.length).toBeGreaterThanOrEqual(3); // welcome + lang confirm + help
  });

  test('should handle language switching', async ({ page, apiClient }) => {
    // Send /start to initiate conversation
    const startUpdate = apiClient.createTextMessage('/start', 12345, 12345);
    await apiClient.sendUpdate(startUpdate);
    await page.waitForTimeout(500);

    // Clear messages to focus on language switching
    apiClient.clearMessages();

    // Test switching to Russian
    const ruLangUpdate = apiClient.createCallbackQuery('lang:ru', 12345);
    await apiClient.sendUpdate(ruLangUpdate);
    await page.waitForTimeout(500);

    // Test switching to English
    const enLangUpdate = apiClient.createCallbackQuery('lang:en', 12345);
    await apiClient.sendUpdate(enLangUpdate);
    await page.waitForTimeout(500);

    const messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThanOrEqual(2); // One message per language switch
  });

  test('should handle unknown commands gracefully', async ({ page, apiClient }) => {
    // Send an unknown command
    const unknownUpdate = apiClient.createTextMessage('/unknown_command', 12345, 12345);
    await apiClient.sendUpdate(unknownUpdate);
    await page.waitForTimeout(500);

    const messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThan(0);

    // Bot should respond with some kind of error or help message
    const response = messages[0];
    expect(response.text).toBeTruthy();
    expect(response.text.length).toBeGreaterThan(0);
  });

  test('should respond to multiple users independently', async ({ page, apiClient }) => {
    // User 1 sends /start
    const user1Start = apiClient.createTextMessage('/start', 11111, 11111);
    await apiClient.sendUpdate(user1Start);
    await page.waitForTimeout(300);

    // User 2 sends /start
    const user2Start = apiClient.createTextMessage('/start', 22222, 22222);
    await apiClient.sendUpdate(user2Start);
    await page.waitForTimeout(300);

    const messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThanOrEqual(2);

    // Both users should receive responses
    const user1Messages = messages.filter(msg => msg.chat.id === 11111);
    const user2Messages = messages.filter(msg => msg.chat.id === 22222);
    
    expect(user1Messages.length).toBeGreaterThan(0);
    expect(user2Messages.length).toBeGreaterThan(0);
  });
});


