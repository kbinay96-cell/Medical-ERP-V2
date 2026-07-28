# Medical ERP V2 - Module 01: Login & Dashboard

Production-grade foundation module for the Medical ERP V2 rebuild.
Everything future module (Company, Supplier, Customer, Item, Purchase,
Sales, etc.) is built on top of this: MVC layering, the centralized
Date Engine, the Authentication/Authorization stack, logging, and
error handling all follow the patterns established here.

## What's included

| Layer   | Files |
|---------|-------|
| UI      | `ui/login.ui`, `ui/ui_login.py`, `ui/dashboard.ui`, `ui/ui_dashboard.py` |
| Screens | `screens/login_screen.py`, `screens/dashboard_screen.py` |
| Engines | `engines/authentication_engine.py`, `authorization_engine.py`, `session_manager.py`, `password_manager.py`, `audit_logger.py`, `license_manager.py`, `subscription_manager.py`, `date_engine.py`, `theme_engine.py`, `dashboard_engine.py` |
| Models  | `models/user_model.py`, `role_model.py`, `company_model.py`, `financialyear_model.py`, `dashboard_model.py` |
| Utils   | `utils/login_validator.py`, `utils/message.py`, `utils/app_logger.py` |
| DB      | `database/db.py`, `database/schema_auth.sql`, `database/schema_calendar.sql`, `database/migrate_bscalendar.py` |
| Config  | `config/settings.py` |
| Tests   | `tests/` (30 unit/integration tests) |
| Style   | `resources/style.qss` (Light), `resources/dark_style.qss` (Dark) |

## Setup

### 1. Install dependencies

```
pip install -r requirements.txt
```

### 2. Create the PostgreSQL database

```sql
CREATE DATABASE medical_erp_v2;
```

Edit `database/db.py` and set your real PostgreSQL username/password
in `DB_CONFIG`.

### 3. Run the schema scripts (in this order)

```
psql -U postgres -d medical_erp_v2 -f database/schema_calendar.sql
psql -U postgres -d medical_erp_v2 -f database/schema_auth.sql
```

(Or paste their contents into pgAdmin's Query Tool and execute.)

### 4. Import real BS<->AD calendar data from V1

This ERP is BS-first: every BS<->AD conversion goes through the
centralized Date Engine (`engines/date_engine.py`), which is backed
by a real calendar reference table (`bscalendar`) rather than a
formula, because the Nepali calendar's month lengths are not
computable from a simple formula.

If your V1 project (`Medical-ERP` folder) already has a populated
`bscalendar` table, reuse that real data:

1. Edit `database/migrate_bscalendar.py` and set your V1 database
   connection details in `V1_DB_CONFIG`.
2. Run:
   ```
   python database/migrate_bscalendar.py
   ```

If you don't have V1's calendar data, `bscalendar` will simply be
empty and BS<->AD conversion will report "calendar data unavailable"
until it is imported - the app still runs, it just can't do that
specific conversion yet.

### 5. Create your first user and role

```sql
-- Roles are already seeded by schema_auth.sql. Find the Administrator role id:
SELECT roleid FROM roles WHERE rolename = 'Administrator';

-- Create a company (needed for the Login screen's Company dropdown):
INSERT INTO company (companyid, companyname) VALUES ('COM001', 'My Pharmacy');

-- Create a financial year:
INSERT INTO financialyear (financialyear, startbsdate, endbsdate, isactive)
VALUES ('2082/2083', '2082-04-01', '2083-03-32', TRUE);
```

Then create your admin user from Python (since passwords must be
hashed - never insert a plain-text password directly):

```python
from models.user_model import create_user
create_user(
    username="admin",
    plain_password="Admin@12345",
    fullname="Administrator",
    roleid=1,             # the Administrator roleid from above
    companyid="COM001",
    created_by="system",
)
```

### 6. Run the application

```
python main.py
```

## Running the tests

```
python -m unittest discover -s tests -v
```

## License / Subscription

This ERP currently runs **unrestricted** - `engines/license_manager.py`
and `engines/subscription_manager.py` allow login when no `license`
or `subscription` row exists yet. Once you're ready to sell/license
this product to other pharmacies, insert real rows into those two
tables and the existing validation logic will start enforcing them
automatically - no code changes needed.

## UI/UX polish pass (this update)

Business logic (Authentication Engine, Session Manager, Authorization,
Models, Database, Login Flow, Dashboard Logic, Date Engine) was **not**
touched in this update - only presentation:

- Login redesigned as a centered "card" with a branding panel on the
  left and the login form in a card on the right (all original widget
  names kept, so nothing broke).
- Dashboard's KPI cards now use a shared, icon-capable card builder.
- `resources/icons/` - 27 simple, generic SVG line icons (`stroke="currentColor"`
  so they automatically tint with the active theme). Not copied from
  any icon pack - drawn as plain geometric shapes.
- `resources/style.qss` / `dark_style.qss` rewritten to explicitly set
  a foreground color for every background color, on every widget type
  (labels, buttons, inputs, group boxes, lists/trees/tables, status
  bar, menus, tooltips) - this is what fixes the earlier white-on-white
  text bug: nothing is left to inherit the OS palette anymore.
- Forgot Password and Language buttons are now wired (previously
  dead): Forgot Password shows the required administrator-managed
  message; Language opens a real dialog (`screens/language_dialog.py`)
  backed by `utils/language_manager.py` - English is fully functional,
  Hindi/Nepali are registered and selectable but not yet translated
  (by design, so nothing is faked).
- Dashboard's search box now really filters the sidebar menu tree as
  you type (`DashboardScreen._filter_sidebar_menu`) - the single
  place future Global Search (Company/Supplier/Customer/Item/
  Purchase/Sales/Invoice/Reports/Settings) will be added later.
- Tooltips + status tips added to every interactive control on both
  screens; buddy labels and explicit tab order added to the Login
  form for keyboard accessibility.

## Notes on this delivery

- All Python files pass syntax checking and have no unused imports
  (verified with an AST-based scan).
- 30 automated tests pass, covering password hashing/policy, login
  input validation, the Date Engine's pure-logic functions, and the
  full Authentication Engine workflow (success, wrong password,
  locked account, empty input, and an unexpected-exception
  crash-safety case) via mocked dependencies.
- `.ui` files could not be verified by actually opening them in Qt
  Designer in this environment (no GUI/Qt Designer available here),
  but they were validated as well-formed XML and their widget names
  were cross-checked against the generated `ui_*.py` files. Please
  do open them once in Qt Designer on your machine as a final check
  before building on top of them.
- KPI cards on the Dashboard (Today's Sales, Stock Value, etc.) query
  real tables and will show real numbers once the Purchase/Sales/Stock
  modules are built - they intentionally show 0 for now rather than
  fabricated numbers.
