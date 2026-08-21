# Purchase Module — Part 1 (Database schema & Models)

What this adds
- DB migration: database/migrations/0001_purchase_schema.sql
- Models:
  - models/purchase_invoice_model.py
  - models/purchase_order_model.py
  - models/purchase_return_model.py (Phase-2)
- ItemModel extension (snippet): models/__patch__/item_model_addition.txt
- Settings seeds that create purchase.* settings in the settings table.

Where to place files
- SQL migration -> database/migrations/0001_purchase_schema.sql
- Models -> models/<filename>.py
- Patch snippet -> models/__patch__/item_model_addition.txt

How to apply (recommended)
1) Create and switch to a feature branch:
   git checkout -b feature/purchase-module-part1

2) Add files (example in Linux/macOS):
   mkdir -p database/migrations models/__patch__
   # create files with the content provided in this PR

3) Run DB migration
   - If you have a migration framework: add this SQL as migration 0001 and run.
   - Or run directly (careful, backup your DB first):
     psql -h <host> -U <user> -d <db> -f database/migrations/0001_purchase_schema.sql

4) Add ItemModel method
   - Paste the snippet from models/__patch__/item_model_addition.txt into models/item_model.py inside the ItemModel class.

5) Commit & push
   git add database/migrations/0001_purchase_schema.sql models/purchase_*.py models/__patch__/item_model_addition.txt README_purchase_module.md
   git commit -m "Add Purchase module Part-1: migrations + models (PO, Invoice, Return) and ItemModel low-stock helper"
   git push origin feature/purchase-module-part1

6) Open a Pull Request on GitHub from feature/purchase-module-part1 -> main (or default branch). Add reviewers and test DB run.

Testing tips
- Run unit-level checks by importing the models and calling basic methods (requires configured DB).
- For initial smoke test, create the tables in a dev DB and run simple INSERT via psql to ensure schema is valid.
- Ensure models database.db.get_connection() resolves to your configured database connection.

Notes & assumptions
- Models are SQL-only; no business rules or validation here; all business logic belongs to Engines (Part-2).
- The insert_* methods accept dictionaries and perform dynamic INSERT. The Engine layer must populate audit stamps (created_by, created_at_bs etc.) according to project conventions.
- The SQL uses PostgreSQL features (REGEXP_REPLACE) for sequence extraction. If you run on a different DB adapt those functions.

If you want, I can:
- Convert these into a single unified git patch (.patch) you can apply with git am.
- Create a PR for you if you add me as a collaborator (I attempted push earlier but lacked permissions).

Good luck — paste these files into your repo and tell me when you're ready for Part‑2 (Engines, Validators, DTOs, and business rules). I can also generate example unit tests for these models if you want.