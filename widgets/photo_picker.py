"""
=========================================================
Medical ERP V2
Photo Picker Widget (reusable across every module)
---------------------------------------------------------
A square photo preview with Upload / Change / Remove
actions. Used by the Customer Form today; meant to be
reused unchanged by Supplier, Company, Employee, Doctor,
and Patient forms later (per the Customer Master spec's
"Future Ready" requirement).

This widget never touches the database or the filesystem
outside of reading the chosen file for preview - actually
copying the file into resources/images/<subfolder>/ happens
in utils.image_manager, orchestrated by the owning Engine
(see engines.customer_engine) once a customer_code exists.
That is why this widget only *stages* a choice and reports
it via get_photo_update() - it never writes an image itself.
=========================================================
"""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QSizePolicy

PREVIEW_SIZE = 140
PHOTO_FILE_FILTER = "Images (*.jpg *.jpeg *.png *.webp)"
PLACEHOLDER_ICON = "resources/icons/user.svg"


class PhotoPicker(QWidget):
    """Emits `photo_staged()` whenever the user picks or removes a photo."""

    photo_staged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._existing_photo_path: str | None = None
        self._staged_source_path: str | None = None
        self._remove_requested = False

        self._build_ui()
        self._show_placeholder()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.preview_label = QLabel()
        self.preview_label.setObjectName("lblCustomerPhotoPreview")
        self.preview_label.setFixedSize(QSize(PREVIEW_SIZE, PREVIEW_SIZE))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setScaledContents(False)
        layout.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignHCenter)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)

        self.btn_upload = QPushButton("Upload Photo")
        self.btn_upload.clicked.connect(self._handle_pick_photo)
        buttons_row.addWidget(self.btn_upload)

        self.btn_change = QPushButton("Change")
        self.btn_change.clicked.connect(self._handle_pick_photo)
        buttons_row.addWidget(self.btn_change)

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self._handle_remove_photo)
        buttons_row.addWidget(self.btn_remove)

        layout.addLayout(buttons_row)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # -----------------------------------------------------
    # PUBLIC API
    # -----------------------------------------------------

    def load_existing(self, photo_path: str | None):
        """Call this once when opening the form (Add: None, Edit: the stored photo_path)."""
        self._existing_photo_path = photo_path
        self._staged_source_path = None
        self._remove_requested = False

        if photo_path:
            self._show_pixmap(photo_path)
        else:
            self._show_placeholder()

    def get_photo_update(self) -> dict:
        """
        Returns the extra keys the Customer Engine's create/update
        functions expect for photo changes. Empty dict means "no
        photo change" - the existing photo_path (if any) is left
        untouched by the Engine.
        """
        if self._staged_source_path:
            return {"_photo_source_path": self._staged_source_path}
        if self._remove_requested:
            return {"_remove_photo": True}
        return {}

    # -----------------------------------------------------
    # INTERNAL
    # -----------------------------------------------------

    def _handle_pick_photo(self):
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose Customer Photo", "", PHOTO_FILE_FILTER)
        if not chosen:
            return

        self._staged_source_path = chosen
        self._remove_requested = False
        self._show_pixmap(chosen)
        self.photo_staged.emit()

    def _handle_remove_photo(self):
        self._staged_source_path = None
        self._remove_requested = True
        self._show_placeholder()
        self.photo_staged.emit()

    def _show_pixmap(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._show_placeholder()
            return

        scaled = pixmap.scaled(
            PREVIEW_SIZE, PREVIEW_SIZE,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.btn_upload.hide()
        self.btn_change.show()
        self.btn_remove.show()

    def _show_placeholder(self):
        icon_pixmap = QIcon(PLACEHOLDER_ICON).pixmap(QSize(48, 48))
        self.preview_label.setPixmap(icon_pixmap)
        self.btn_upload.show()
        self.btn_change.hide()
        self.btn_remove.hide()


def host_photo_beside_scroll(root_layout, scroll_widget: QWidget) -> "PhotoPicker":
    """Places PhotoPicker to the left of an existing scroll area (Customer pattern)."""
    picker = PhotoPicker(scroll_widget.parentWidget())
    index = root_layout.indexOf(scroll_widget)
    root_layout.removeWidget(scroll_widget)
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(16)
    h.addWidget(picker, 0, Qt.AlignmentFlag.AlignTop)
    h.addWidget(scroll_widget, 1)
    root_layout.insertWidget(index, row, 1)
    return picker