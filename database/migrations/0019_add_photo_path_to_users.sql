-- Migration 0019: Add photo_path column to users table.
-- user_engine.py / user_model.py already read/write this
-- column (photo support, same pattern as items/suppliers),
-- but it was never added to the users table itself.

ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_path VARCHAR(500);