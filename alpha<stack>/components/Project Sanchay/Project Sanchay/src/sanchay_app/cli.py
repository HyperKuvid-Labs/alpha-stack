import argparse
import asyncio
import logging
import os
import sys
from typing import Optional, Dict, List

# Local application imports
from sanchay_app.core.job_manager import JobManager
from sanchay_app.utils.logging_config import setup_logging
from config.settings import settings

logger = logging.getLogger(__name__)

def validate_local_path(path: str) -> str:
    """Validates if the provided local filesystem path exists and is accessible."""
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Error: Path '{path}' does not exist.")
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"Error: Path '{path}' is not a directory.")
    if not os.access(path, os.R_OK):
        raise argparse.ArgumentTypeError(f"Error: Insufficient read permissions for path '{path}'.")
    return os.path.abspath(path)

async def handle_scan(args: argparse.Namespace):
    """Handles the 'scan' command, starting a new processing job."""
    target_path = args.path
    job_type = args.type
    output_dir = args.output
    job_name = args.name

    # Validate local paths if not a recognized cloud path
    if not target_path.startswith(("s3://", "minio://")): # Extend with other cloud prefixes if needed
        target_path = validate_local_path(target_path)
    
    # Optional output directory validation
    if output_dir:
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                raise argparse.ArgumentTypeError(f"Error: Could not create output directory '{output_dir}': {e}")
        if not os.access(output_dir, os.W_OK):
            raise argparse.ArgumentTypeError(f"Error: Insufficient write permissions for output directory '{output_dir}'.")
        output_dir = os.path.abspath(output_dir)

    logger.info(f"Starting new scan job: Path='{target_path}', Type='{job_type}', Name='{job_name or 'N/A'}'")

    job_manager = JobManager()
    try:
        job_id = await job_manager.start_job(
            path=target_path,
            job_type=job_type,
            output_path=output_dir,
            job_name=job_name
        )
        print(f"Job started with ID: {job_id}")
        print("Monitoring progress...")

        # Display real-time progress
        async for progress in job_manager.subscribe_to_job_progress(job_id):
            status = progress.get('status', 'UNKNOWN')
            processed_count = progress.get('processed_count', 0)
            total_count = progress.get('total_count', 0)
            percentage = progress.get('percentage', 0.0)
            files_per_sec = progress.get('files_per_second', 0.0)
            elapsed_time = progress.get('elapsed_time', 0.0)
            message = progress.get('message', '')

            if total_count > 0:
                progress_str = f"Progress: {percentage:.2f}% ({processed_count}/{total_count} files) | Status: {status} | {files_per_sec:.2f} files/s | Elapsed: {elapsed_time:.2f}s"
            else:
                progress_str = f"Progress: {processed_count} files processed | Status: {status} | Elapsed: {elapsed_time:.2f}s"
            
            if message:
                progress_str += f" | Msg: {message}"

            # Use carriage return to overwrite line for dynamic progress updates
            sys.stdout.write(f"\r{progress_str.ljust(os.get_terminal_size().columns - 1)}") # Pad to clear previous longer lines
            sys.stdout.flush()

            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                break
        
        sys.stdout.write("\n") # Newline after final progress update
        final_status = await job_manager.get_job_status(job_id)
        if final_status:
            print(f"Job {job_id} finished with status: {final_status.get('status', 'UNKNOWN')}")
            if final_status.get('status') == 'FAILED':
                print(f"Error details: {final_status.get('error', 'N/A')}")
            elif final_status.get('status') == 'COMPLETED' and final_status.get('results_summary'):
                print("Results Summary:")
                for key, value in final_status['results_summary'].items():
                    print(f"  {key}: {value}")
        else:
            print(f"Could not retrieve final status for job {job_id}.")

    except Exception as e:
        logger.error(f"Failed to start or monitor job: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)

async def handle_jobs_list(args: argparse.Namespace):
    """Handles the 'jobs list' command, showing active and completed jobs."""
    job_manager = JobManager()
    try:
        jobs = await job_manager.list_jobs()
        if not jobs:
            print("No jobs found.")
            return

        print(f"{'ID':<40} {'Name':<25} {'Type':<15} {'Status':<10} {'Progress':<10} {'Started':<20}")
        print("-" * 120)
        for job in jobs:
            job_id = job.get('id', 'N/A')
            name = job.get('name', 'N/A')
            job_type = job.get('type', 'N/A')
            status = job.get('status', 'N/A')
            progress = f"{job.get('percentage', 0.0):.1f}%"
            started_at = job.get('started_at', 'N/A')
            print(f"{job_id:<40} {name:<25} {job_type:<15} {status:<10} {progress:<10} {started_at:<20}")

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)

async def handle_jobs_status(args: argparse.Namespace):
    """Handles the 'jobs status' command, showing details for a specific job."""
    job_id = args.job_id
    job_manager = JobManager()
    try:
        status = await job_manager.get_job_status(job_id)
        if not status:
            print(f"Job with ID '{job_id}' not found.")
            sys.exit(1)

        print(f"--- Job Status: {job_id} ---")
        for key, value in status.items():
            if key == 'results_summary' and value:
                print("Results Summary:")
                for res_key, res_value in value.items():
                    print(f"  {res_key}: {res_value}")
            elif key == 'error' and value:
                print(f"Error Details: {value}")
            else:
                print(f"{key.replace('_', ' ').title()}: {value}")

    except Exception as e:
        logger.error(f"Failed to get status for job '{job_id}': {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)

def main():
    """Main entry point for the Sanchay CLI."""
    setup_logging() # Initialize logging early

    parser = argparse.ArgumentParser(
        description="Sanchay: A high-performance file collection and processing tool.\n"
                    "Use it to scan local directories or cloud storage for various tasks.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # --- Scan Command ---
    scan_parser = subparsers.add_parser(
        "scan",
        help="Start a new file processing job.",
        description="Scans a directory (local or cloud) and performs specified processing tasks.\n\n"
                    "Available job types:\n"
                    "  checksum   - Generates checksums for all files.\n"
                    "  duplicates - Identifies duplicate files based on content hash.\n"
                    "  metadata   - Extracts basic file metadata (size, dates, etc.)."
    )
    scan_parser.add_argument(
        "path",
        type=str,
        help="The target directory or cloud storage path to scan (e.g., /path/to/my/data or s3://my-bucket/prefix)"
    )
    scan_parser.add_argument(
        "--type",
        "-t",
        choices=["checksum", "duplicates", "metadata"],
        default="checksum",
        help="Type of processing job to run."
    )
    scan_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Optional local directory to save detailed results (e.g., duplicate lists, reports). "
             "Will be created if it does not exist."
    )
    scan_parser.add_argument(
        "--name",
        "-n",
        type=str,
        help="Optional name for the job (defaults to a generated UUID if not provided)."
    )
    scan_parser.set_defaults(func=handle_scan)

    # --- Jobs Command ---
    jobs_parser = subparsers.add_parser(
        "jobs",
        help="Manage and view processing jobs."
    )
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", help="Jobs subcommands", required=True)

    # Jobs List Command
    jobs_list_parser = jobs_subparsers.add_parser(
        "list",
        help="List all active and completed jobs."
    )
    jobs_list_parser.set_defaults(func=handle_jobs_list)

    # Jobs Status Command
    jobs_status_parser = jobs_subparsers.add_parser(
        "status",
        help="Show detailed status for a specific job."
    )
    jobs_status_parser.add_argument(
        "job_id",
        type=str,
        help="The ID of the job to retrieve status for."
    )
    jobs_status_parser.set_defaults(func=handle_jobs_status)

    args = parser.parse_args()

    # The func attribute is set by set_defaults in each subparser
    if hasattr(args, "func"):
        try:
            # Run the async handler function
            asyncio.run(args.func(args))
        except argparse.ArgumentTypeError as e:
            print(f"CLI Argument Error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            logger.critical(f"An unhandled error occurred: {e}", exc_info=True)
            print(f"An unexpected error occurred: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # This case should ideally not be reached if required=True is used for subparsers
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()