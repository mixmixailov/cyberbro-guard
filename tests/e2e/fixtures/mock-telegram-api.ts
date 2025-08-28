/**
 * Mock Telegram Bot API server for E2E testing
 * 
 * This lightweight server stubs Telegram Bot API endpoints to enable
 * testing without real Telegram infrastructure.
 */
import express from 'express';
import { Server } from 'http';

export interface MockTelegramBot {
  id: number;
  is_bot: boolean;
  first_name: string;
  username: string;
  can_join_groups: boolean;
  can_read_all_group_messages: boolean;
  supports_inline_queries: boolean;
}

export interface MockUpdate {
  update_id: number;
  message?: {
    message_id: number;
    from: {
      id: number;
      is_bot: boolean;
      first_name: string;
      username?: string;
    };
    chat: {
      id: number;
      type: string;
      first_name?: string;
      username?: string;
    };
    date: number;
    text?: string;
  };
  callback_query?: {
    id: string;
    from: {
      id: number;
      is_bot: boolean;
      first_name: string;
      username?: string;
    };
    message?: any;
    data?: string;
  };
  pre_checkout_query?: {
    id: string;
    from: {
      id: number;
      is_bot: boolean;
      first_name: string;
      username?: string;
    };
    currency: string;
    total_amount: number;
    invoice_payload: string;
  };
}

export class MockTelegramAPI {
  private app: express.Application;
  private server: Server | null = null;
  private port: number;
  private botToken: string;
  
  // Mock state
  private sentMessages: any[] = [];
  private webhookUrl: string | null = null;
  private webhookSecret: string | null = null;
  private updateIdCounter = 1;

  constructor(port: number = 8001, botToken: string = 'test:1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA') {
    this.port = port;
    this.botToken = botToken;
    this.app = express();
    this.setupRoutes();
  }

  private setupRoutes(): void {
    this.app.use(express.json());
    
    // Log all requests for debugging
    this.app.use((req, res, next) => {
      console.log(`[Mock Telegram API] ${req.method} ${req.path}`, req.body);
      next();
    });

    // Get bot info
    this.app.get(`/bot${this.botToken}/getMe`, (req, res) => {
      res.json({
        ok: true,
        result: {
          id: 123456789,
          is_bot: true,
          first_name: 'CyberBro Guard Test',
          username: 'cyberbro_guard_test_bot',
          can_join_groups: true,
          can_read_all_group_messages: false,
          supports_inline_queries: false
        }
      });
    });

    // Set webhook
    this.app.post(`/bot${this.botToken}/setWebhook`, (req, res) => {
      this.webhookUrl = req.body.url;
      this.webhookSecret = req.body.secret_token;
      console.log(`[Mock Telegram API] Webhook set to: ${this.webhookUrl}`);
      res.json({
        ok: true,
        result: true,
        description: 'Webhook is set'
      });
    });

    // Get webhook info
    this.app.get(`/bot${this.botToken}/getWebhookInfo`, (req, res) => {
      res.json({
        ok: true,
        result: {
          url: this.webhookUrl || '',
          has_custom_certificate: false,
          pending_update_count: 0,
          last_error_date: 0,
          max_connections: 40,
          allowed_updates: ['message', 'callback_query', 'pre_checkout_query']
        }
      });
    });

    // Send message
    this.app.post(`/bot${this.botToken}/sendMessage`, (req, res) => {
      const message = {
        message_id: Date.now(),
        from: {
          id: 123456789,
          is_bot: true,
          first_name: 'CyberBro Guard Test',
          username: 'cyberbro_guard_test_bot'
        },
        chat: {
          id: req.body.chat_id,
          type: 'private'
        },
        date: Math.floor(Date.now() / 1000),
        text: req.body.text
      };
      
      this.sentMessages.push(message);
      console.log(`[Mock Telegram API] Sent message: ${req.body.text}`);
      
      res.json({
        ok: true,
        result: message
      });
    });

    // Edit message text
    this.app.post(`/bot${this.botToken}/editMessageText`, (req, res) => {
      const message = {
        message_id: req.body.message_id || Date.now(),
        from: {
          id: 123456789,
          is_bot: true,
          first_name: 'CyberBro Guard Test',
          username: 'cyberbro_guard_test_bot'
        },
        chat: {
          id: req.body.chat_id,
          type: 'private'
        },
        date: Math.floor(Date.now() / 1000),
        text: req.body.text,
        edit_date: Math.floor(Date.now() / 1000)
      };
      
      res.json({
        ok: true,
        result: message
      });
    });

    // Answer callback query
    this.app.post(`/bot${this.botToken}/answerCallbackQuery`, (req, res) => {
      console.log(`[Mock Telegram API] Answered callback query: ${req.body.text || 'OK'}`);
      res.json({
        ok: true,
        result: true
      });
    });

    // Answer pre checkout query
    this.app.post(`/bot${this.botToken}/answerPreCheckoutQuery`, (req, res) => {
      console.log(`[Mock Telegram API] Answered pre-checkout query: ${req.body.ok ? 'APPROVED' : 'DENIED'}`);
      res.json({
        ok: true,
        result: true
      });
    });

    // Create invoice link
    this.app.post(`/bot${this.botToken}/createInvoiceLink`, (req, res) => {
      const invoiceLink = `https://t.me/cyberbro_guard_test_bot?start=invoice_${Date.now()}`;
      console.log(`[Mock Telegram API] Created invoice link: ${invoiceLink}`);
      res.json({
        ok: true,
        result: invoiceLink
      });
    });

    // Health check for the mock server
    this.app.get('/health', (req, res) => {
      res.json({ status: 'ok', messages_sent: this.sentMessages.length });
    });

    // Debug endpoints
    this.app.get('/debug/messages', (req, res) => {
      res.json({ messages: this.sentMessages });
    });

    this.app.post('/debug/clear', (req, res) => {
      this.sentMessages = [];
      res.json({ status: 'cleared' });
    });

    // Error handler
    this.app.use((err: any, req: any, res: any, next: any) => {
      console.error('[Mock Telegram API] Error:', err);
      res.status(500).json({
        ok: false,
        error_code: 500,
        description: 'Internal server error'
      });
    });
  }

  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server = this.app.listen(this.port, () => {
        console.log(`[Mock Telegram API] Server running on port ${this.port}`);
        resolve();
      });
      
      this.server.on('error', (err) => {
        console.error('[Mock Telegram API] Server error:', err);
        reject(err);
      });
    });
  }

  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => {
          console.log('[Mock Telegram API] Server stopped');
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  // Helper methods for testing
  getSentMessages(): any[] {
    return [...this.sentMessages];
  }

  clearMessages(): void {
    this.sentMessages = [];
  }

  // Simulate incoming update to webhook
  async sendUpdate(update: MockUpdate): Promise<boolean> {
    if (!this.webhookUrl) {
      console.warn('[Mock Telegram API] No webhook URL set, cannot send update');
      return false;
    }

    try {
      const fetch = (await import('node-fetch')).default;
      const headers: any = {
        'Content-Type': 'application/json',
        'User-Agent': 'TelegramBot/1.0'
      };

      if (this.webhookSecret) {
        headers['X-Telegram-Bot-Api-Secret-Token'] = this.webhookSecret;
      }

      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(update)
      });

      console.log(`[Mock Telegram API] Sent update to webhook: ${response.status}`);
      return response.ok;
    } catch (error) {
      console.error('[Mock Telegram API] Failed to send update:', error);
      return false;
    }
  }

  // Create common test updates
  createTextMessage(text: string, userId: number = 12345, chatId: number = 12345): MockUpdate {
    return {
      update_id: this.updateIdCounter++,
      message: {
        message_id: Date.now(),
        from: {
          id: userId,
          is_bot: false,
          first_name: 'Test User',
          username: 'testuser'
        },
        chat: {
          id: chatId,
          type: 'private',
          first_name: 'Test User',
          username: 'testuser'
        },
        date: Math.floor(Date.now() / 1000),
        text
      }
    };
  }

  createCallbackQuery(data: string, userId: number = 12345): MockUpdate {
    return {
      update_id: this.updateIdCounter++,
      callback_query: {
        id: `callback_${Date.now()}`,
        from: {
          id: userId,
          is_bot: false,
          first_name: 'Test User',
          username: 'testuser'
        },
        data
      }
    };
  }

  createPreCheckoutQuery(payload: string, amount: number = 100, userId: number = 12345): MockUpdate {
    return {
      update_id: this.updateIdCounter++,
      pre_checkout_query: {
        id: `pre_checkout_${Date.now()}`,
        from: {
          id: userId,
          is_bot: false,
          first_name: 'Test User',
          username: 'testuser'
        },
        currency: 'XTR',
        total_amount: amount,
        invoice_payload: payload
      }
    };
  }
}


