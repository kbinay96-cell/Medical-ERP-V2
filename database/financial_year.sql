CREATE TABLE IF NOT EXISTS financial_year (
    financial_year_id         SERIAL PRIMARY KEY,
    fy_label                      VARCHAR(20) NOT NULL UNIQUE,   -- e.g. '2082/83'
    start_date_ad                   DATE NOT NULL,
    end_date_ad                       DATE NOT NULL,
    start_date_bs                       VARCHAR(10) NOT NULL,
    end_date_bs                           VARCHAR(10) NOT NULL,
    status                                   VARCHAR(20) NOT NULL DEFAULT 'Open',   -- 'Open' | 'Closed'
    closing_journal_entry_id                   INTEGER REFERENCES journal_entry(journal_entry_id),   -- set once Year End Closing has run

    CONSTRAINT chk_fy_status CHECK (status IN ('Open', 'Closed'))
);