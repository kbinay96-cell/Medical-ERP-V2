-- Migration 0021: Support graduated lockout backoff.
-- Tracks consecutive lockouts per user so lock duration can
-- progressively lengthen (register_failed_attempt in
-- models/user_model.py). Reset to 0 on any successful
-- login/unlock (reset_failed_attempts), NOT on auto-unlock
-- expiry, so repeat offenders keep escalating.

ALTER TABLE users ADD COLUMN IF NOT EXISTS lockoutcount INTEGER NOT NULL DEFAULT 0;