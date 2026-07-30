"""
=========================================================
Medical ERP V2
Company Master - Automated Tests
---------------------------------------------------------
These tests run against a real (dev/test) PostgreSQL
database, matching the project's existing convention of
testing models/engines against the actual DB rather than
mocking it. Run against a disposable test database only.
=========================================================
"""

import unittest
from engines.company_engine import (
    CompanyEngine, CompanyValidationError, DuplicateCompanyError,
    CompanyNotFoundError
)


class TestCompanyMaster(unittest.TestCase):

    def setUp(self):
        self.sample = {"companyname": "Unit Test Pharmacy", "city": "Kathmandu"}

    def test_create_requires_name(self):
        with self.assertRaises(CompanyValidationError):
            CompanyEngine.create_company({"companyname": ""}, created_by="tester")

    def test_create_and_duplicate_block(self):
        cid = CompanyEngine.create_company(self.sample, created_by="tester")
        self.assertTrue(cid.startswith("COM"))
        with self.assertRaises(DuplicateCompanyError):
            CompanyEngine.create_company(self.sample, created_by="tester")
        CompanyEngine.delete_company(cid, deleted_by="tester")  # cleanup

    def test_update_not_found(self):
        with self.assertRaises(CompanyNotFoundError):
            CompanyEngine.update_company("COM999", self.sample, modified_by="tester")

    def test_soft_delete_and_restore(self):
        cid = CompanyEngine.create_company(
            {"companyname": "Delete Restore Co"}, created_by="tester"
        )
        self.assertTrue(CompanyEngine.delete_company(cid, deleted_by="tester"))
        active_results = CompanyEngine.search_companies(status_filter="all")
        self.assertFalse(any(c["companyid"] == cid for c in active_results))

        self.assertTrue(CompanyEngine.restore_company(cid, modified_by="tester"))
        restored_results = CompanyEngine.search_companies(status_filter="all")
        self.assertTrue(any(c["companyid"] == cid for c in restored_results))
        CompanyEngine.delete_company(cid, deleted_by="tester")  # cleanup

    def test_search(self):
        cid = CompanyEngine.create_company(
            {"companyname": "Searchable Pharmacy XYZ"}, created_by="tester"
        )
        results = CompanyEngine.search_companies(search_term="XYZ")
        self.assertTrue(any(c["companyid"] == cid for c in results))
        CompanyEngine.delete_company(cid, deleted_by="tester")  # cleanup


if __name__ == "__main__":
    unittest.main()
