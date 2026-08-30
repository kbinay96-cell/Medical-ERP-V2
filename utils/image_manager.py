"""
=========================================================
Medical ERP V2
Image Manager (reusable across every module)
---------------------------------------------------------
Purpose:
    One generic component for "entity has an optional photo"
    - used by Customer Master today, and meant to be reused
    unchanged by Supplier, Company, Employee, Doctor, and
    Patient later (per the Customer Master spec's "Future
    Ready" requirement).

    Only ever stores/returns a relative file path such as
    "resources/images/customers/CUS-0001.jpg" - the database
    never holds binary image data.

Layout on disk:
    resources/images/<subfolder>/<filename_stem><ext>
    e.g. resources/images/customers/CUS-0001.jpg
         resources/images/suppliers/SUP-0004.png   (future)
=========================================================
"""

import shutil
from pathlib import Path

from utils.app_logger import get_logger

logger = get_logger()

IMAGES_BASE_DIR = Path("resources/images")
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def save_image(source_path: str, subfolder: str, filename_stem: str) -> tuple[bool, str]:
    """
    Copies an image the user picked (source_path, anywhere on
    disk) into resources/images/<subfolder>/<filename_stem><ext>,
    replacing any existing file for that stem first (so a
    "Change Photo" never leaves the old file orphaned).

    Returns (success, relative_path_or_error_message). On
    success the second value is the relative path to store in
    the entity's photo_path column.
    """
    source = Path(source_path)
    extension = source.suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported image format '{extension}'. Use jpg, jpeg, png, or webp."

    if not source.is_file():
        return False, f"Source image not found: {source_path}"

    target_dir = IMAGES_BASE_DIR / subfolder
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.exception(f"save_image: could not create folder '{target_dir}': {e}")
        return False, "Could not create the images folder."

    _remove_existing_variants(target_dir, filename_stem)

    target_path = target_dir / f"{filename_stem}{extension}"
    try:
        shutil.copyfile(source, target_path)
    except OSError as e:
        logger.exception(f"save_image: could not copy '{source_path}' to '{target_path}': {e}")
        return False, "Could not save the image file."

    return True, str(target_path).replace("\\", "/")


def apply_entity_photo(
    payload: dict,
    *,
    existing_path: str | None,
    subfolder: str,
    filename_stem: str,
) -> str | None:
    """
    Consumes Screen-staged keys `_photo_source_path` / `_remove_photo`
    (from widgets.photo_picker.PhotoPicker.get_photo_update) and returns
    the path the Model should persist. Engines call this; Screens do not.
    """
    photo_source = payload.pop("_photo_source_path", None)
    remove_photo = payload.pop("_remove_photo", False)

    if remove_photo:
        delete_image(existing_path)
        return None
    if photo_source:
        photo_ok, photo_result = save_image(photo_source, subfolder, filename_stem)
        if photo_ok:
            return photo_result
        logger.warning("apply_entity_photo: photo not saved for '%s': %s", filename_stem, photo_result)
        return existing_path
    return existing_path


def delete_image(relative_path: str | None) -> bool:
    """
    Removes an entity's photo file from disk. Safe to call with
    None or a path that no longer exists - always returns True
    in that case, since the end state (no file) is achieved.
    """
    if not relative_path:
        return True

    path = Path(relative_path)
    try:
        if path.is_file():
            path.unlink()
    except OSError as e:
        logger.exception(f"delete_image: could not remove '{relative_path}': {e}")
        return False

    return True


def _remove_existing_variants(target_dir: Path, filename_stem: str) -> None:
    """
    An entity might change photo format between saves (jpg ->
    png), so clear any existing file with the same stem
    regardless of extension before writing the new one.
    """
    for ext in ALLOWED_EXTENSIONS:
        existing = target_dir / f"{filename_stem}{ext}"
        if existing.is_file():
            try:
                existing.unlink()
            except OSError as e:
                logger.exception(f"_remove_existing_variants: could not remove '{existing}': {e}")
