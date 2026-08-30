"""
engines/company_engine.py

Company Master business logic - Medical ERP V2.
Mirrors engines/supplier_engine.py's shape exactly (DTO in/out,
shared exceptions from engines/exceptions.py, no SQL, no UI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models import company_model
from models.company_model import CompanyModelError
from validators.company_validator import validate_company_data


@dataclass
class CompanyDTO:
    company_id: str
    company_name: str
    address: Optional[str]
    contact_person: Optional[str]
    mobile_no: Optional[str]
    phone_no: Optional[str]
    email: Optional[str]
    pan_vat_no: Optional[str]
    registration_no: Optional[str]
    dda_no: Optional[str]
    logo_path: Optional[str]
    country: Optional[str]
    remarks: Optional[str]
    status: str
    is_deleted: bool


def _row_to_dto(row: dict) -> CompanyDTO:
    return CompanyDTO(
        company_id=row.get("companyid"),
        company_name=row.get("companyname"),
        address=row.get("address"),
        contact_person=row.get("contactperson"),
        mobile_no=row.get("mobileno"),
        phone_no=row.get("phone"),
        email=row.get("email"),
        pan_vat_no=row.get("panno"),
        registration_no=row.get("registrationno"),
        dda_no=row.get("ddano"),
        logo_path=row.get("logopath"),
        country=row.get("country"),
        remarks=row.get("remarks"),
        status=row.get("status") or "Active",
        is_deleted=bool(row.get("isdeleted")),
    )


class CompanyEngine:
    """Business logic for the Company Master. Screens call ONLY this class."""

    def create_company(self, data: dict, current_user_id) -> CompanyDTO:
        errors = validate_company_data(data)
        if errors:
            raise ValidationError(errors)

        try:
            if company_model.company_name_exists(data["companyname"]):
                raise DuplicateRecordError(
                    f"A company named '{data['companyname']}' already exists."
                )
            company_id = company_model.insert_company(data, created_by=str(current_user_id))
            row = company_model.get_company_by_id(company_id)
            return _row_to_dto(row)
        except CompanyModelError as exc:
            raise RuntimeError(str(exc)) from exc

    def update_company(self, company_id: str, data: dict, current_user_id) -> CompanyDTO:
        errors = validate_company_data(data)
        if errors:
            raise ValidationError(errors)

        try:
            existing = company_model.get_company_by_id(company_id)
            if not existing or existing.get("isdeleted"):
                raise RecordNotFoundError(f"Company '{company_id}' not found.")

            if company_model.company_name_exists(data["companyname"], exclude_companyid=company_id):
                raise DuplicateRecordError(
                    f"A company named '{data['companyname']}' already exists."
                )

            company_model.update_company(company_id, data, modified_by=str(current_user_id))

            status = data.get("status")
            if status in ("Active", "Inactive") and status != existing.get("status"):
                company_model.set_company_status(company_id, status, modified_by=str(current_user_id))

            row = company_model.get_company_by_id(company_id)
            return _row_to_dto(row)
        except CompanyModelError as exc:
            raise RuntimeError(str(exc)) from exc

    def delete_company(self, company_id: str, current_user_id) -> None:
        existing = company_model.get_company_by_id(company_id)
        if not existing or existing.get("isdeleted"):
            raise RecordNotFoundError(f"Company '{company_id}' not found.")
        try:
            company_model.soft_delete_company(company_id, deleted_by=str(current_user_id))
        except CompanyModelError as exc:
            raise RuntimeError(str(exc)) from exc

    def restore_company(self, company_id: str, current_user_id) -> CompanyDTO:
        existing = company_model.get_company_by_id(company_id)
        if not existing or not existing.get("isdeleted"):
            raise RecordNotFoundError(f"Company '{company_id}' not found or not deleted.")
        try:
            company_model.restore_company(company_id, modified_by=str(current_user_id))
            row = company_model.get_company_by_id(company_id)
            return _row_to_dto(row)
        except CompanyModelError as exc:
            raise RuntimeError(str(exc)) from exc

    def get_company(self, company_id: str) -> CompanyDTO:
        row = company_model.get_company_by_id(company_id)
        if not row:
            raise RecordNotFoundError(f"Company '{company_id}' not found.")
        return _row_to_dto(row)

    def search_companies(
        self,
        search_text: Optional[str] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 500,
    ) -> Tuple[List[CompanyDTO], int]:
        status_filter = "all"
        if status == "Active":
            status_filter = "active"
        elif status == "Inactive":
            status_filter = "inactive"

        try:
            rows = company_model.list_companies(
                search_term=search_text,
                status_filter=status_filter,
                include_deleted=include_deleted,
            )
        except CompanyModelError as exc:
            raise RuntimeError(str(exc)) from exc

        total = len(rows)
        start = (page - 1) * page_size
        page_rows = rows[start:start + page_size]
        return [_row_to_dto(r) for r in page_rows], total


__all__ = ["CompanyEngine", "CompanyDTO"]
