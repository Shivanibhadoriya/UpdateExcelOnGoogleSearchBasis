"""Application orchestration entry point for CompanyLocationEnricher."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from cache_service import CacheService
from config import Config, load_config
from excel_service import ExcelService, ExcelServiceError
from location_service import LocationService
from logger import configure_logging
from search_service import SearchServiceError, SerpApiSearchService


SUCCESS = 0
PROCESSING_ERROR = 1
CONFIGURATION_ERROR = 2


@dataclass
class ProcessingSummary:
    """Counters recorded while orchestrating workbook enrichment."""

    workbooks_processed: int = 0
    companies_processed: int = 0
    cache_hits: int = 0
    locations_found: int = 0
    locations_not_found: int = 0
    search_failures: int = 0


def main() -> int:
    """Run application orchestration and return a process-compatible exit code."""

    try:
        config = load_config()
    except ValueError as error:
        logging.getLogger(__name__).error("Configuration error: %s", error)
        return CONFIGURATION_ERROR

    logger = configure_logging(config)
    try:
        summary = _run_enrichment(config, logger)
    except (ExcelServiceError, OSError, ValueError) as error:
        logger.exception("Application processing failed: %s", error)
        return PROCESSING_ERROR
    except Exception:
        logger.exception("Unexpected application failure")
        return PROCESSING_ERROR

    logger.info(
        "Processing complete: workbooks=%d companies=%d cache_hits=%d "
        "locations_found=%d locations_not_found=%d search_failures=%d",
        summary.workbooks_processed,
        summary.companies_processed,
        summary.cache_hits,
        summary.locations_found,
        summary.locations_not_found,
        summary.search_failures,
    )
    return SUCCESS


def _run_enrichment(config: Config, logger: logging.Logger) -> ProcessingSummary:
    """Coordinate configured services to enrich every input workbook."""

    excel_service = ExcelService()
    search_service = SerpApiSearchService(config)
    location_service = LocationService()
    cache_service = CacheService(config.cache_directory)
    summary = ProcessingSummary()

    for input_path in excel_service.find_workbooks(config.input_directory):
        _process_workbook(
            config,
            input_path,
            excel_service,
            search_service,
            location_service,
            cache_service,
            summary,
            logger,
        )
    return summary


def _process_workbook(
    config: Config,
    input_path: Path,
    excel_service: ExcelService,
    search_service: SerpApiSearchService,
    location_service: LocationService,
    cache_service: CacheService,
    summary: ProcessingSummary,
    logger: logging.Logger,
) -> None:
    """Coordinate enrichment and output saving for one workbook."""

    workbook, worksheet = excel_service.prepare_workbook(input_path)
    company_column = excel_service.find_company_column(worksheet)
    location_column = excel_service.ensure_location_column(worksheet)

    for row_index, company_name in excel_service.iter_company_rows(
        worksheet, company_column
    ):
        summary.companies_processed += 1
        location = cache_service.get(company_name)
        if location is not None:
            summary.cache_hits += 1
        else:
            try:
                search_result = search_service.search(company_name)
                location = location_service.extract_location(search_result)
            except SearchServiceError as error:
                summary.search_failures += 1
                logger.warning("Search failed for %r: %s", company_name, error)
                continue

            if location is not None:
                cache_service.put(company_name, location)

        if location is None:
            summary.locations_not_found += 1
            logger.info("No reliable location found for %r", company_name)
            continue

        excel_service.write_location(worksheet, row_index, location_column, location)
        summary.locations_found += 1

    output_path = excel_service.output_path(input_path, config.output_directory)
    excel_service.save_workbook(workbook, output_path)
    summary.workbooks_processed += 1
    logger.info("Saved enriched workbook: %s", output_path)


if __name__ == "__main__":
    raise SystemExit(main())
