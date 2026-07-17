"""Read, validate, and prepare company-location Excel workbooks."""

from pathlib import Path
from typing import Union

from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet


PathLike = Union[str, Path]


class ExcelServiceError(Exception):
    """Base exception for workbook processing failures."""


class WorkbookLoadError(ExcelServiceError):
    """Raised when an Excel workbook cannot be opened."""


class CompanyColumnNotFoundError(ExcelServiceError):
    """Raised when the active worksheet has no Company column."""


class WorkbookSaveError(ExcelServiceError):
    """Raised when an Excel workbook cannot be saved."""


class ExcelService:
    """Provide operations for the application's input Excel workbook."""

    def load_workbook(self, workbook_path: PathLike) -> Workbook:
        """Open and return the workbook at ``workbook_path``.

        Raises:
            WorkbookLoadError: If the path is missing or the workbook is invalid.
        """
        path = Path(workbook_path)

        if not path.is_file():
            raise WorkbookLoadError(f"Workbook not found: {path}")

        try:
            return load_workbook(path)
        except (InvalidFileException, OSError, ValueError) as error:
            raise WorkbookLoadError(
                f"Unable to open workbook '{path}': {error}"
            ) from error

    def get_active_worksheet(self, workbook: Workbook) -> Worksheet:
        """Return the workbook's active worksheet.

        Raises:
            ExcelServiceError: If the workbook has no active worksheet.
        """
        try:
            return workbook.active
        except (AttributeError, IndexError) as error:
            raise ExcelServiceError(
                "The workbook does not contain an active worksheet."
            ) from error

    def find_company_column(self, worksheet: Worksheet) -> int:
        """Return the one-based index of the Company header in row one.

        Header matching ignores leading and trailing whitespace and case.

        Raises:
            CompanyColumnNotFoundError: If the Company column is absent.
        """
        for column_index, cell in enumerate(worksheet[1], start=1):
            value = cell.value
            if isinstance(value, str) and value.strip().casefold() == "company":
                return column_index

        raise CompanyColumnNotFoundError(
            "The active worksheet must contain a 'Company' header in row 1."
        )

    def ensure_location_column(self, worksheet: Worksheet) -> int:
        """Return the Location column index, creating its header if needed."""
        for column_index, cell in enumerate(worksheet[1], start=1):
            value = cell.value
            if isinstance(value, str) and value.strip().casefold() == "location":
                return column_index

        location_column = worksheet.max_column + 1
        worksheet.cell(row=1, column=location_column, value="Location")
        return location_column

    def save_workbook(self, workbook: Workbook, workbook_path: PathLike) -> None:
        """Save ``workbook`` to ``workbook_path``.

        Raises:
            WorkbookSaveError: If the workbook cannot be saved.
        """
        path = Path(workbook_path)

        try:
            workbook.save(path)
        except (OSError, ValueError) as error:
            raise WorkbookSaveError(
                f"Unable to save workbook to '{path}': {error}"
            ) from error

    def prepare_workbook(self, workbook_path: PathLike) -> tuple[Workbook, Worksheet]:
        """Open a workbook and ensure its active sheet is ready for enrichment.

        The active worksheet must have a Company column. A Location column is
        added when absent; the updated workbook is saved to the source path.
        """
        workbook = self.load_workbook(workbook_path)
        worksheet = self.get_active_worksheet(workbook)
        self.find_company_column(worksheet)
        self.ensure_location_column(worksheet)
        self.save_workbook(workbook, workbook_path)
        return workbook, worksheet
