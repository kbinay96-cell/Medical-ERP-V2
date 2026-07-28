"""
engines/exceptions.py

Shared exception hierarchy for Engine-layer errors. Kept generic (not
Supplier-specific in naming) so future master modules (Customer, Item, etc.)
reuse the same base classes instead of duplicating exception logic --
consistent with the project's "No Duplicate Logic" rule.
"""


class EngineError(Exception):
    """Base class for all business-rule/engine-layer errors."""


class ValidationError(EngineError):
    """Raised when input fails business validation. Carries the full error list."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors) if errors else "Validation failed.")


class RecordNotFoundError(EngineError):
    """Raised when an operation targets a record that does not exist (or is deleted)."""


class DuplicateRecordError(EngineError):
    """Raised when a uniqueness rule is violated outside the normal validation path
    (e.g. a race condition caught at the database constraint level)."""
