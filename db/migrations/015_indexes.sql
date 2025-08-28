-- Add useful indexes for performance
CREATE INDEX IF NOT EXISTS idx_payments_tg_id ON payments (tg_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_tg_id ON subscriptions (tg_id);
CREATE INDEX IF NOT EXISTS idx_user_state_composite ON user_state (user_id, chat_id);










