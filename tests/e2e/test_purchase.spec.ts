import { test, expect } from './fixtures';

test.describe('Purchase Flow', () => {
  const TEST_USER_ID = 54321;
  const TEST_CHAT_ID = 54321;

  test.beforeEach(async ({ page, apiClient }) => {
    // Navigate to the application
    await page.goto('/');
    
    // Initialize user with /start
    const startUpdate = apiClient.createTextMessage('/start', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(startUpdate);
    await page.waitForTimeout(500);
    
    // Clear messages to focus on purchase flow
    apiClient.clearMessages();
  });

  test('should complete purchase flow: /buy -> SuccessfulPayment -> /status shows active', async ({ 
    page, 
    apiClient 
  }) => {
    // Step 1: Initiate purchase with /buy
    const buyUpdate = apiClient.createTextMessage('/buy', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(buyUpdate);
    await page.waitForTimeout(1000);

    // Check that bot responded with purchase options
    let messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThan(0);
    
    const buyResponse = messages.find(msg => 
      msg.text && (
        msg.text.includes('plan') || 
        msg.text.includes('Plan') ||
        msg.text.includes('buy') ||
        msg.text.includes('purchase') ||
        msg.text.includes('subscribe')
      )
    );
    expect(buyResponse).toBeTruthy();

    // Step 2: Select a plan (e.g., premium plan)
    const planUpdate = apiClient.createCallbackQuery('buy:premium', TEST_USER_ID);
    await apiClient.sendUpdate(planUpdate);
    await page.waitForTimeout(500);

    // Bot should send invoice or payment link
    messages = apiClient.getSentMessages();
    const invoiceMessage = messages.find(msg => 
      msg.text && (
        msg.text.includes('invoice') ||
        msg.text.includes('payment') ||
        msg.text.includes('pay') ||
        msg.text.includes('XTR') ||
        msg.text.includes('Stars')
      )
    );
    expect(invoiceMessage).toBeTruthy();

    // Step 3: Simulate pre-checkout query
    const preCheckoutUpdate = apiClient.createPreCheckoutQuery(
      'premium_plan_payload', 
      100, // 100 XTR
      TEST_USER_ID
    );
    await apiClient.sendUpdate(preCheckoutUpdate);
    await page.waitForTimeout(500);

    // Step 4: Simulate successful payment
    const successfulPaymentUpdate = {
      update_id: Date.now(),
      message: {
        message_id: Date.now(),
        from: {
          id: TEST_USER_ID,
          is_bot: false,
          first_name: 'Test User',
          username: 'testuser'
        },
        chat: {
          id: TEST_CHAT_ID,
          type: 'private',
          first_name: 'Test User',
          username: 'testuser'
        },
        date: Math.floor(Date.now() / 1000),
        successful_payment: {
          currency: 'XTR',
          total_amount: 100,
          invoice_payload: 'premium_plan_payload',
          telegram_payment_charge_id: `charge_${Date.now()}`,
          provider_payment_charge_id: `provider_${Date.now()}`
        }
      }
    };
    
    await apiClient.sendUpdate(successfulPaymentUpdate);
    await page.waitForTimeout(1000);

    // Bot should confirm the payment
    messages = apiClient.getSentMessages();
    const paymentConfirmation = messages.find(msg => 
      msg.text && (
        msg.text.includes('success') ||
        msg.text.includes('Success') ||
        msg.text.includes('thank') ||
        msg.text.includes('Thank') ||
        msg.text.includes('confirmed') ||
        msg.text.includes('active')
      )
    );
    expect(paymentConfirmation).toBeTruthy();

    // Step 5: Check status shows active subscription
    apiClient.clearMessages();
    const statusUpdate = apiClient.createTextMessage('/status', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(statusUpdate);
    await page.waitForTimeout(500);

    messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThan(0);
    
    const statusMessage = messages.find(msg => 
      msg.text && (
        msg.text.includes('active') ||
        msg.text.includes('Active') ||
        msg.text.includes('premium') ||
        msg.text.includes('Premium') ||
        msg.text.includes('subscribed')
      )
    );
    expect(statusMessage).toBeTruthy();
  });

  test('should handle payment cancellation', async ({ page, apiClient }) => {
    // Initiate purchase
    const buyUpdate = apiClient.createTextMessage('/buy', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(buyUpdate);
    await page.waitForTimeout(500);

    // Select plan
    const planUpdate = apiClient.createCallbackQuery('buy:premium', TEST_USER_ID);
    await apiClient.sendUpdate(planUpdate);
    await page.waitForTimeout(500);

    // Send pre-checkout query but don't follow with successful payment
    const preCheckoutUpdate = apiClient.createPreCheckoutQuery(
      'premium_plan_payload', 
      100,
      TEST_USER_ID
    );
    await apiClient.sendUpdate(preCheckoutUpdate);
    await page.waitForTimeout(500);

    // Check status - should still show free plan
    apiClient.clearMessages();
    const statusUpdate = apiClient.createTextMessage('/status', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(statusUpdate);
    await page.waitForTimeout(500);

    const messages = apiClient.getSentMessages();
    const statusMessage = messages[0];
    expect(statusMessage.text).toBeTruthy();
    expect(statusMessage.text).not.toMatch(/active.*premium/i);
  });

  test('should handle multiple plan options', async ({ page, apiClient }) => {
    // Initiate purchase
    const buyUpdate = apiClient.createTextMessage('/buy', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(buyUpdate);
    await page.waitForTimeout(500);

    const messages = apiClient.getSentMessages();
    const buyResponse = messages[0];
    expect(buyResponse.text).toBeTruthy();

    // Test different plan selections
    const plans = ['basic', 'premium', 'pro'];
    
    for (const plan of plans) {
      apiClient.clearMessages();
      const planUpdate = apiClient.createCallbackQuery(`buy:${plan}`, TEST_USER_ID);
      await apiClient.sendUpdate(planUpdate);
      await page.waitForTimeout(300);

      const planMessages = apiClient.getSentMessages();
      expect(planMessages.length).toBeGreaterThan(0);
    }
  });

  test('should prevent duplicate payment processing', async ({ page, apiClient }) => {
    // Complete first payment
    const buyUpdate = apiClient.createTextMessage('/buy', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(buyUpdate);
    await page.waitForTimeout(300);

    const planUpdate = apiClient.createCallbackQuery('buy:premium', TEST_USER_ID);
    await apiClient.sendUpdate(planUpdate);
    await page.waitForTimeout(300);

    const chargeId = `charge_${Date.now()}`;
    const successfulPaymentUpdate = {
      update_id: Date.now(),
      message: {
        message_id: Date.now(),
        from: {
          id: TEST_USER_ID,
          is_bot: false,
          first_name: 'Test User'
        },
        chat: {
          id: TEST_CHAT_ID,
          type: 'private'
        },
        date: Math.floor(Date.now() / 1000),
        successful_payment: {
          currency: 'XTR',
          total_amount: 100,
          invoice_payload: 'premium_plan_payload',
          telegram_payment_charge_id: chargeId,
          provider_payment_charge_id: `provider_${Date.now()}`
        }
      }
    };
    
    await apiClient.sendUpdate(successfulPaymentUpdate);
    await page.waitForTimeout(500);

    const messagesAfterFirstPayment = apiClient.getSentMessages();
    const firstPaymentCount = messagesAfterFirstPayment.length;

    // Send the same payment again (same charge_id)
    await apiClient.sendUpdate(successfulPaymentUpdate);
    await page.waitForTimeout(500);

    const messagesAfterDuplicate = apiClient.getSentMessages();
    
    // Should not process duplicate payment (idempotency)
    expect(messagesAfterDuplicate.length).toBe(firstPaymentCount);
  });

  test('should handle refunded payments', async ({ page, apiClient }) => {
    // Complete a payment first
    const buyUpdate = apiClient.createTextMessage('/buy', TEST_USER_ID, TEST_CHAT_ID);
    await apiClient.sendUpdate(buyUpdate);
    await page.waitForTimeout(300);

    const planUpdate = apiClient.createCallbackQuery('buy:premium', TEST_USER_ID);
    await apiClient.sendUpdate(planUpdate);
    await page.waitForTimeout(300);

    const chargeId = `charge_${Date.now()}`;
    const successfulPaymentUpdate = {
      update_id: Date.now(),
      message: {
        message_id: Date.now(),
        from: {
          id: TEST_USER_ID,
          is_bot: false,
          first_name: 'Test User'
        },
        chat: {
          id: TEST_CHAT_ID,
          type: 'private'
        },
        date: Math.floor(Date.now() / 1000),
        successful_payment: {
          currency: 'XTR',
          total_amount: 100,
          invoice_payload: 'premium_plan_payload',
          telegram_payment_charge_id: chargeId,
          provider_payment_charge_id: `provider_${Date.now()}`
        }
      }
    };
    
    await apiClient.sendUpdate(successfulPaymentUpdate);
    await page.waitForTimeout(500);

    // Now simulate a refund
    const refundedPaymentUpdate = {
      update_id: Date.now() + 1,
      message: {
        message_id: Date.now() + 1,
        from: {
          id: TEST_USER_ID,
          is_bot: false,
          first_name: 'Test User'
        },
        chat: {
          id: TEST_CHAT_ID,
          type: 'private'
        },
        date: Math.floor(Date.now() / 1000),
        refunded_payment: {
          currency: 'XTR',
          total_amount: 100,
          invoice_payload: 'premium_plan_payload',
          telegram_payment_charge_id: chargeId
        }
      }
    };

    apiClient.clearMessages();
    await apiClient.sendUpdate(refundedPaymentUpdate);
    await page.waitForTimeout(500);

    // Bot should acknowledge the refund
    const messages = apiClient.getSentMessages();
    expect(messages.length).toBeGreaterThan(0);
    
    const refundMessage = messages.find(msg => 
      msg.text && (
        msg.text.includes('refund') ||
        msg.text.includes('Refund') ||
        msg.text.includes('cancelled') ||
        msg.text.includes('reverted')
      )
    );
    expect(refundMessage).toBeTruthy();
  });
});


