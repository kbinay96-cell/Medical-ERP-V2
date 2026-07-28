-- =========================================================
-- Medical ERP V2 - BS Calendar Reference Table
-- ---------------------------------------------------------
-- This table is the single source of truth for BS<->AD
-- conversion (see engines/date_engine.py). It must be
-- populated with real Nepali calendar data - see
-- database/migrate_bscalendar.py to import it from the
-- existing V1 database, which already has this data.
-- =========================================================

CREATE TABLE IF NOT EXISTS bscalendar (
    calendarid      BIGSERIAL PRIMARY KEY,
    bsdate          VARCHAR(10) NOT NULL UNIQUE,   -- e.g. '2083-04-05'
    addate          DATE NOT NULL UNIQUE,
    bsyear          INTEGER NOT NULL,
    bsmonth         INTEGER NOT NULL,
    bsday           INTEGER NOT NULL,
    monthnameen     VARCHAR(20) NOT NULL,
    weekdayno       INTEGER NOT NULL,
    weekdayen       VARCHAR(20) NOT NULL,
    financialyear   VARCHAR(20) NOT NULL,
    isweekend       BOOLEAN DEFAULT FALSE,
    isholiday       BOOLEAN DEFAULT FALSE,
    holidayname     VARCHAR(100),
    createddate     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bscalendar_addate ON bscalendar(addate);
CREATE INDEX IF NOT EXISTS idx_bscalendar_bsdate ON bscalendar(bsdate);
