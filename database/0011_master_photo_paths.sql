-- Master photo/logo paths (relative file paths only — never BLOBs).
-- Customer already has photo_path; Item, Supplier, and User reuse the same pattern.

ALTER TABLE item ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);
ALTER TABLE supplier ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);

COMMENT ON COLUMN item.photo_path IS 'Relative image path, e.g. resources/images/items/ITM-0001.jpg';
COMMENT ON COLUMN supplier.photo_path IS 'Relative image path, e.g. resources/images/suppliers/SUP-0001.jpg';
COMMENT ON COLUMN users.photo_path IS 'Relative image path, e.g. resources/images/users/admin.jpg';
