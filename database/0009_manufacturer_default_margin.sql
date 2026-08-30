ALTER TABLE manufacturer
ADD COLUMN IF NOT EXISTS default_margin_percent NUMERIC(5,2);