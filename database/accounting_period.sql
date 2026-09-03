CREATE TABLE IF NOT EXISTS accounting_period (
    accounting_period_id      SERIAL PRIMARY KEY,
    financial_year_id             INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    period_label                     VARCHAR(20) NOT NULL,   -- e.g. 'Shrawan 2082'
    start_date_ad                      DATE NOT NULL,
    end_date_ad                          DATE NOT NULL,
    status                                  VARCHAR(20) NOT NULL DEFAULT 'Open',   -- 'Open' | 'Locked'
    locked_by                                 INTEGER,
    locked_at_ad                                TIMESTAMP,
    reopened_by                                   INTEGER,           -- controlled-reopening mechanism (confirmed scope)
    reopened_at_ad                                  TIMESTAMP,
    reopen_reason                                     TEXT,

    CONSTRAINT chk_period_status CHECK (status IN ('Open', 'Locked'))
);