import datetime
import nepali_datetime
from database.db import get_connection

# 2000 BS se 2100 BS tak (~50+ saal aage tak) generate karega
START_AD = datetime.date(1943, 4, 14)   # roughly 2000 BS ke shuruaat ke aas-paas
END_AD = datetime.date(2033, 4, 13)     # roughly 2090 BS tak (50 saal se zyada aage)

MONTH_NAMES_EN = [
    "Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def get_financial_year(bs_year, bs_month):
    if bs_month <= 3:
        return f"{bs_year - 1}/{bs_year}"
    return f"{bs_year}/{bs_year + 1}"

def main():
    conn = get_connection()
    cur = conn.cursor()

    current_ad = START_AD
    inserted = 0

    while current_ad <= END_AD:
        bs_date = nepali_datetime.date.from_datetime_date(current_ad)

        bs_date_str = f"{bs_date.year:04d}-{bs_date.month:02d}-{bs_date.day:02d}"
        weekday_no = current_ad.weekday()  # 0=Monday ... 6=Sunday
        weekday_en = WEEKDAY_NAMES[weekday_no]
        is_weekend = (weekday_en == "Saturday")
        financial_year = get_financial_year(bs_date.year, bs_date.month)

        cur.execute(
            """
            INSERT INTO bscalendar (
                bsdate, addate, bsyear, bsmonth, bsday, monthnameen,
                weekdayno, weekdayen, financialyear, isweekend, isholiday
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (bsdate) DO NOTHING
            """,
            (
                bs_date_str, current_ad, bs_date.year, bs_date.month, bs_date.day,
                MONTH_NAMES_EN[bs_date.month - 1], weekday_no, weekday_en,
                financial_year, is_weekend, False,
            )
        )
        inserted += 1
        current_ad += datetime.timedelta(days=1)

        if inserted % 1000 == 0:
            conn.commit()
            print(f"{inserted} rows processed...")

    conn.commit()
    print(f"DONE. Total rows processed: {inserted}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()