"""
=========================================================
Medical ERP V2
Manufacturer Master - Automated Tests
---------------------------------------------------------
Unlike tests/test_company_master.py (which runs against a
real database), these tests inject a fake in-memory Model
into ManufacturerEngine -- the same dependency-injection
seam SupplierEngine/ManufacturerEngine were built with --
so the Short Name de-duplication rule (the most important
business rule in this module) and the validator can be
verified fast, without a live PostgreSQL instance.
=========================================================
"""

import unittest

from engines.exceptions import DuplicateRecordError, ValidationError
from engines.manufacturer_engine import ManufacturerEngine, generate_short_name_base


class _FakeManufacturerModel:
    """Minimal in-memory stand-in for models.manufacturer_model.ManufacturerModel."""

    def __init__(self):
        self._rows = {}
        self._next_id = 1

    def insert(self, data):
        new_id = self._next_id
        self._next_id += 1
        row = dict(data)
        row["manufacturer_id"] = new_id
        row["is_deleted"] = False
        row["updated_by"] = None
        row["updated_at_ad"] = None
        row["updated_at_bs"] = None
        row["deleted_by"] = None
        row["deleted_at_ad"] = None
        row["deleted_at_bs"] = None
        self._rows[new_id] = row
        return new_id

    def update(self, manufacturer_id, data):
        row = self._rows.get(manufacturer_id)
        if row is None or row["is_deleted"]:
            return False
        row.update(data)
        return True

    def get_by_id(self, manufacturer_id, include_deleted=False):
        row = self._rows.get(manufacturer_id)
        if row is None:
            return None
        if row["is_deleted"] and not include_deleted:
            return None
        return dict(row)

    def exists_by_name(self, name, exclude_id=None):
        return any(
            r["manufacturer_name"].lower() == name.lower() and r["manufacturer_id"] != exclude_id and not r["is_deleted"]
            for r in self._rows.values()
        )

    def exists_by_code(self, code, exclude_id=None):
        return any(
            r["manufacturer_code"].lower() == code.lower() and r["manufacturer_id"] != exclude_id and not r["is_deleted"]
            for r in self._rows.values()
        )

    def exists_by_short_name(self, short_name, exclude_id=None):
        return any(
            r["manufacturer_short_name"].lower() == short_name.lower() and r["manufacturer_id"] != exclude_id and not r["is_deleted"]
            for r in self._rows.values()
        )

    def get_last_code_sequence(self, prefix):
        max_seq = 0
        for r in self._rows.values():
            code = r["manufacturer_code"]
            if code.startswith(prefix):
                try:
                    max_seq = max(max_seq, int(code[len(prefix):]))
                except ValueError:
                    pass
        return max_seq

    def soft_delete(self, manufacturer_id, deleted_by, deleted_at_ad, deleted_at_bs):
        row = self._rows.get(manufacturer_id)
        if row is None or row["is_deleted"]:
            return False
        row["is_deleted"] = True
        row["deleted_by"] = deleted_by
        row["deleted_at_ad"] = deleted_at_ad
        row["deleted_at_bs"] = deleted_at_bs
        return True

    def restore(self, manufacturer_id, updated_by, updated_at_ad, updated_at_bs):
        row = self._rows.get(manufacturer_id)
        if row is None or not row["is_deleted"]:
            return False
        row["is_deleted"] = False
        row["deleted_by"] = None
        row["deleted_at_ad"] = None
        row["deleted_at_bs"] = None
        row["updated_by"] = updated_by
        row["updated_at_ad"] = updated_at_ad
        row["updated_at_bs"] = updated_at_bs
        return True


def _make_engine() -> ManufacturerEngine:
    # date_engine=None / settings_engine=None skips the lazy-loader entirely
    # (constructor treats an explicit None as "already resolved to nothing"),
    # so tests never depend on a real database or bscalendar being populated.
    return ManufacturerEngine(model=_FakeManufacturerModel(), date_engine=None, settings_engine=None)


class TestShortNameGeneration(unittest.TestCase):
    def test_first_word_extraction(self):
        self.assertEqual(generate_short_name_base("Sun Pharma"), "Sun")
        self.assertEqual(generate_short_name_base("Cipla Ltd"), "Cipla")
        self.assertEqual(generate_short_name_base("Abbott India"), "Abbott")
        self.assertEqual(generate_short_name_base("Himalaya Wellness"), "Himalaya")
        self.assertEqual(generate_short_name_base("SingleWord"), "SingleWord")
        self.assertEqual(generate_short_name_base("   "), "")


class TestManufacturerEngine(unittest.TestCase):
    def test_create_generates_code_and_short_name(self):
        engine = _make_engine()
        dto = engine.create_manufacturer({"manufacturer_name": "Sun Pharma", "country": "India"}, current_user_id=1)
        self.assertEqual(dto.manufacturer_code, "MFG-0001")
        self.assertEqual(dto.manufacturer_short_name, "Sun")
        self.assertEqual(dto.status, "Active")

    def test_duplicate_short_name_is_suffixed(self):
        engine = _make_engine()
        first = engine.create_manufacturer({"manufacturer_name": "Sun Pharma"}, current_user_id=1)
        second = engine.create_manufacturer({"manufacturer_name": "Sun Labs"}, current_user_id=1)
        third = engine.create_manufacturer({"manufacturer_name": "Sun Biotech"}, current_user_id=1)

        self.assertEqual(first.manufacturer_short_name, "Sun")
        self.assertEqual(second.manufacturer_short_name, "Sun1")
        self.assertEqual(third.manufacturer_short_name, "Sun2")

    def test_duplicate_name_blocked(self):
        engine = _make_engine()
        engine.create_manufacturer({"manufacturer_name": "Cipla Ltd"}, current_user_id=1)
        with self.assertRaises(ValidationError):
            engine.create_manufacturer({"manufacturer_name": "Cipla Ltd"}, current_user_id=1)

    def test_mandatory_name(self):
        engine = _make_engine()
        with self.assertRaises(ValidationError):
            engine.create_manufacturer({"manufacturer_name": ""}, current_user_id=1)

    def test_manual_code_uniqueness(self):
        engine = _make_engine()
        engine.create_manufacturer({"manufacturer_name": "Abbott India", "manufacturer_code": "MFG-CUSTOM"}, current_user_id=1)
        with self.assertRaises(ValidationError):
            engine.create_manufacturer({"manufacturer_name": "Abbott Labs", "manufacturer_code": "MFG-CUSTOM"}, current_user_id=1)

    def test_update_regenerates_short_name_on_rename(self):
        engine = _make_engine()
        dto = engine.create_manufacturer({"manufacturer_name": "Cipla Ltd"}, current_user_id=1)
        updated = engine.update_manufacturer(dto.manufacturer_id, {"manufacturer_name": "Himalaya Wellness"}, current_user_id=1)
        self.assertEqual(updated.manufacturer_short_name, "Himalaya")

    def test_soft_delete_and_restore(self):
        engine = _make_engine()
        dto = engine.create_manufacturer({"manufacturer_name": "Delete Restore Mfg"}, current_user_id=1)
        engine.delete_manufacturer(dto.manufacturer_id, current_user_id=1)
        self.assertTrue(engine.get_manufacturer(dto.manufacturer_id, include_deleted=True).is_deleted)

        restored = engine.restore_manufacturer(dto.manufacturer_id, current_user_id=1)
        self.assertFalse(restored.is_deleted)


if __name__ == "__main__":
    unittest.main()
