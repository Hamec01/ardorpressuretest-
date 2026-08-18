import argparse
import os
import sys
from pathlib import Path

from wika_report.config import load_config
from wika_report.file_processor import process_batch
from wika_report.logging_setup import setup_logging


def main() -> int:
    # If launched without command-line arguments, open GUI mode
    if len(sys.argv) == 1:
        from wika_report.gui import launch_gui
        launch_gui()
        return 0

    parser = argparse.ArgumentParser(
        description="Automatic parsing, cleaning and report generation for WIKA CPG1500 CSV files"
    )
    parser.add_argument("--input", type=str, default="input", help="Path to input CSV folder (default: input)")
    parser.add_argument("--output", type=str, default="output", help="Path to output folder (default: output)")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode without saving files")
    parser.add_argument("--file", type=str, default=None, help="Process single CSV file")
    parser.add_argument("--gui", action="store_true", help="Force launch GUI interface")

    args = parser.parse_args()

    if args.gui:
        from wika_report.gui import launch_gui
        launch_gui()
        return 0

    project_root = Path.cwd()
    input_dir = (project_root / args.input).resolve()
    output_dir = (project_root / args.output).resolve()
    logs_dir = output_dir / "logs"
    processed_dir = (project_root / "processed").resolve()
    failed_dir = (project_root / "failed").resolve()
    config_file = (project_root / args.config).resolve()

    logger = setup_logging(logs_dir)
    logger.info("============================================================")
    logger.info("  Starting WIKA CPG1500 Graph Processor")
    logger.info("============================================================")

    try:
        config = load_config(config_file)
        logger.info(f"Configuration loaded from: {config_file.name}")
    except Exception as e:
        logger.error(f"[CRITICAL ERROR] Failed to load configuration: {e}")
        return 1

    specific_file_path = Path(args.file).resolve() if args.file else None
    if specific_file_path and not specific_file_path.exists():
        logger.error(f"[CRITICAL ERROR] File does not exist: {specific_file_path}")
        return 1

    if args.dry_run:
        logger.info("[DRY-RUN] Dry run mode enabled.")

    results = process_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
        config=config,
        specific_file=specific_file_path
    )

    total_found = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total_found - successful

    logger.info("\n============================================================")
    logger.info(f"BATCH SUMMARY:")
    logger.info(f"  Total Found:  {total_found}")
    logger.info(f"  Successful:   {successful}")
    logger.info(f"  Failed:       {failed}")
    logger.info(f"  Output Dir:   {output_dir}")
    logger.info("============================================================\n")

    if config.open_output_folder_after_finish and output_dir.exists() and total_found > 0:
        try:
            if sys.platform == "win32":
                os.startfile(str(output_dir))
        except Exception as e:
            logger.warning(f"Failed to open output folder: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
