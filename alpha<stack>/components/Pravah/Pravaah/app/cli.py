import typer
from typing import Optional, Annotated
from pathlib import Path
import logging
import sys
import uvicorn
import subprocess
import os

from pravah.app.config.settings import get_settings
from pravah.app.db.session import get_db
from pravah.app.db.models.user import User
from pravah.app.auth.jwt import pwd_context
from pravah.app.core.jobs import submit_file_processing_job, get_job_by_id
from pravah.app.core.constants import JobStatus, JobType  # Assuming JobStatus and JobType enums are defined here
from pravah.app.utils.logging import configure_logging

app = typer.Typer(
    name="pravah",
    help="Pravah CLI for administrative and operational tasks.",
    pretty_exceptions_show_locals=False,
)

db_app = typer.Typer(help="Manage database migrations.")
user_app = typer.Typer(help="Manage application users.")
job_app = typer.Typer(help="Trigger and monitor processing jobs.")

app.add_typer(db_app, name="db")
app.add_typer(user_app, name="user")
app.add_typer(job_app, name="job")

logger = logging.getLogger(__name__)

# --- Global Callback and Initialization ---
@app.callback()
def main_callback(
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            "-l",
            help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
            case_sensitive=False,
        ),
    ] = "INFO",
):
    """
    Pravah: High-Performance File & Data Processing Engine CLI.
    """
    try:
        configure_logging(log_level)
        settings = get_settings()  # Load settings early to ensure environment vars are parsed
        logger.debug(f"Pravah CLI started with log level: {log_level}, App Env: {settings.app_env}")
    except Exception as e:
        typer.secho(f"Failed to initialize application settings or logging: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

# --- DB Commands ---
# Calculate the path to alembic.ini relative to this cli.py file
# cli.py is in app/, alembic.ini is in app/db/migrations/
ALEMBIC_INI_PATH = Path(__file__).parent / "db" / "migrations" / "alembic.ini"

def run_alembic_command(command_args: list[str]):
    """Helper function to execute Alembic commands via subprocess."""
    typer.echo(f"Running Alembic command: alembic -c {ALEMBIC_INI_PATH} {' '.join(command_args)}")
    try:
        result = subprocess.run(
            ["alembic", "-c", str(ALEMBIC_INI_PATH)] + command_args,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)} # Add pravah/ to PYTHONPATH
        )
        typer.echo(result.stdout)
        if result.stderr:
            typer.secho(result.stderr, fg=typer.colors.YELLOW)
        return result
    except subprocess.CalledProcessError as e:
        typer.secho(f"Alembic command failed with error: {e.returncode}", fg=typer.colors.RED)
        typer.secho(e.stderr, fg=typer.colors.RED)
        logger.error(f"Alembic command failed: {e.cmd}", exc_info=True)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.secho("Alembic executable not found. Is Alembic installed and in your PATH?", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred while running Alembic: {e}", fg=typer.colors.RED)
        logger.error(f"Unexpected error during Alembic command: {e}", exc_info=True)
        raise typer.Exit(code=1)

@db_app.command("upgrade")
def db_upgrade(
    revision: Annotated[str, typer.Argument(help="The revision to upgrade to (e.g., 'head', a specific revision ID).")] = "head",
    sql: Annotated[bool, typer.Option("--sql", help="Don't emit SQL, instead dump to standard output.")] = False,
    tag: Annotated[Optional[str], typer.Option("--tag", help="Arbitrary 'tag' name for the revision.")] = None,
):
    """
    Applies database migrations to the specified revision (default: head).
    """
    cmd = ["upgrade", revision]
    if sql:
        cmd.append("--sql")
    if tag:
        cmd.extend(["--tag", tag])
    run_alembic_command(cmd)
    typer.secho("Database upgrade complete.", fg=typer.colors.GREEN)

@db_app.command("downgrade")
def db_downgrade(
    revision: Annotated[str, typer.Argument(help="The revision to downgrade to (e.g., '-1', a specific revision ID).")],
    sql: Annotated[bool, typer.Option("--sql", help="Don't emit SQL, instead dump to standard output.")] = False,
    tag: Annotated[Optional[str], typer.Option("--tag", help="Arbitrary 'tag' name for the revision.")] = None,
):
    """
    Reverts database migrations to the specified revision.
    """
    cmd = ["downgrade", revision]
    if sql:
        cmd.append("--sql")
    if tag:
        cmd.extend(["--tag", tag])
    run_alembic_command(cmd)
    typer.secho("Database downgrade complete.", fg=typer.colors.GREEN)

@db_app.command("revision")
def db_revision(
    message: Annotated[Optional[str], typer.Option("-m", "--message", help="Message for the revision.")] = None,
    autogenerate: Annotated[bool, typer.Option("--autogenerate", help="Autogenerate revision script based on model changes.")] = False,
    empty: Annotated[bool, typer.Option("--empty", help="Create an empty revision file (no auto-generated content).")] = False,
):
    """
    Creates a new database migration script.
    Use --autogenerate to detect model changes, or --empty for a blank script.
    """
    if autogenerate and empty:
        typer.secho("Cannot use --autogenerate and --empty together.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    cmd = ["revision"]
    if message:
        cmd.extend(["-m", message])
    if autogenerate:
        cmd.append("--autogenerate")
    elif empty:
        cmd.append("--empty")
    else:
        typer.secho("Please specify either --autogenerate or --empty.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    run_alembic_command(cmd)
    typer.secho("New revision script created.", fg=typer.colors.GREEN)

@db_app.command("current")
def db_current():
    """
    Displays the current database revision.
    """
    run_alembic_command(["current"])

# --- User Commands ---
@user_app.command("create")
def create_user(
    username: Annotated[str, typer.Argument(help="Username for the new user.")],
    password: Annotated[str, typer.Argument(help="Password for the new user.")],
):
    """
    Creates a new application user.
    """
    hashed_password = pwd_context.hash(password)
    try:
        with get_db() as db:
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                typer.secho(f"User '{username}' already exists.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

            new_user = User(username=username, hashed_password=hashed_password)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            typer.secho(f"User '{username}' created successfully with ID: {new_user.id}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error creating user: {e}", fg=typer.colors.RED)
        logger.error(f"Error creating user '{username}': {e}", exc_info=True)
        raise typer.Exit(code=1)

@user_app.command("list")
def list_users():
    """
    Lists all application users.
    """
    try:
        with get_db() as db:
            users = db.query(User).all()
            if not users:
                typer.echo("No users found.")
                return

            typer.echo("Existing Users:")
            for user in users:
                typer.echo(f"  ID: {user.id}, Username: {user.username}, Created: {user.created_at}")
    except Exception as e:
        typer.secho(f"Error listing users: {e}", fg=typer.colors.RED)
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise typer.Exit(code=1)

@user_app.command("delete")
def delete_user(
    username: Annotated[str, typer.Argument(help="Username of the user to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Force deletion without confirmation.")] = False,
):
    """
    Deletes an application user.
    """
    try:
        with get_db() as db:
            user_to_delete = db.query(User).filter(User.username == username).first()
            if not user_to_delete:
                typer.secho(f"User '{username}' not found.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

            if not force:
                confirm = typer.confirm(f"Are you sure you want to delete user '{username}'?")
                if not confirm:
                    typer.echo("Deletion cancelled.")
                    raise typer.Exit()

            db.delete(user_to_delete)
            db.commit()
            typer.secho(f"User '{username}' deleted successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error deleting user: {e}", fg=typer.colors.RED)
        logger.error(f"Error deleting user '{username}': {e}", exc_info=True)
        raise typer.Exit(code=1)

# --- Job Commands ---
@job_app.command("submit")
def submit_job(
    input_path: Annotated[Path, typer.Argument(help="Path to the input directory or file.")],
    output_path: Annotated[Path, typer.Option("--output", "-o", help="Path for the output results.")],
    job_type_str: Annotated[str, typer.Option("--type", "-t", help="Type of processing job (e.g., 'CSV_HEADER_EXTRACT', 'IMAGE_RESIZE').")] = JobType.DEFAULT_PROCESS.value,
    recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Process files recursively in directories.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-d", help="Perform a dry run without actual processing, only validate inputs.")] = False,
):
    """
    Submits a new file processing job to the Pravah engine.
    """
    if not input_path.exists():
        typer.secho(f"Input path '{input_path}' does not exist.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Validate job_type_str against JobType enum
    try:
        job_type = JobType[job_type_str.upper()]
    except KeyError:
        typer.secho(f"Invalid job type '{job_type_str}'. Available types: {[jt.value for jt in JobType]}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not input_path.is_dir() and recursive:
         typer.secho("--recursive is only applicable for directories. Ignoring for file input.", fg=typer.colors.YELLOW)
         recursive = False

    typer.echo(f"Submitting job '{job_type.value}' for '{input_path}'...")
    try:
        job_id = submit_file_processing_job(
            input_path=str(input_path),
            output_path=str(output_path),
            job_type=job_type,
            recursive=recursive,
            dry_run=dry_run
        )
        typer.secho(f"Job submitted successfully! Job ID: {job_id}", fg=typer.colors.GREEN)
        typer.echo(f"You can check its status using: pravah job status {job_id}")
    except Exception as e:
        typer.secho(f"Error submitting job: {e}", fg=typer.colors.RED)
        logger.error(f"Error submitting job: {e}", exc_info=True)
        raise typer.Exit(code=1)

@job_app.command("status")
def job_status(
    job_id: Annotated[str, typer.Argument(help="ID of the job to check.")],
):
    """
    Checks the status and details of a specific processing job.
    """
    try:
        job = get_job_by_id(job_id)
        if job:
            typer.echo("\n--- Job Details ---")
            typer.echo(f"  ID: {job.id}")
            status_color = {
                JobStatus.PENDING: typer.colors.YELLOW,
                JobStatus.RUNNING: typer.colors.BLUE,
                JobStatus.COMPLETED: typer.colors.GREEN,
                JobStatus.FAILED: typer.colors.RED,
                JobStatus.CANCELLED: typer.colors.BRIGHT_MAGENTA,
            }.get(job.status, typer.colors.WHITE)
            typer.secho(f"  Status: {job.status.value}", fg=status_color)
            typer.echo(f"  Job Type: {job.job_type.value if job.job_type else 'N/A'}")
            typer.echo(f"  Input Path: {job.input_path}")
            typer.echo(f"  Output Path: {job.output_path}")
            typer.echo(f"  Created At: {job.created_at.isoformat()}")
            if job.started_at:
                typer.echo(f"  Started At: {job.started_at.isoformat()}")
            if job.completed_at:
                typer.echo(f"  Completed At: {job.completed_at.isoformat()}")
            if job.error_message:
                typer.secho(f"  Error: {job.error_message}", fg=typer.colors.RED)
            if job.progress_details:
                typer.echo(f"  Progress: {job.progress_details}")
            typer.echo("-------------------\n")
        else:
            typer.secho(f"Job with ID '{job_id}' not found.", fg=typer.colors.YELLOW)
    except Exception as e:
        typer.secho(f"Error retrieving job status: {e}", fg=typer.colors.RED)
        logger.error(f"Error retrieving job status for {job_id}: {e}", exc_info=True)
        raise typer.Exit(code=1)

# --- Main App Commands ---
@app.command("serve")
def serve_app(
    host: Annotated[Optional[str], typer.Option("--host", help="Host address to bind to.")] = None,
    port: Annotated[Optional[int], typer.Option("--port", help="Port to listen on.")] = None,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto-reload for development.")] = False,
):
    """
    Starts the Pravah FastAPI web application.
    """
    typer.echo("Starting Pravah FastAPI application...")
    settings = get_settings() # Ensure settings are loaded

    # Override settings with CLI options if provided
    current_host = host if host is not None else settings.api_host
    current_port = port if port is not None else settings.api_port
    current_reload = reload if reload else settings.debug # Use settings.debug as default for reload

    try:
        # Assuming 'main.py' is in 'app/' and contains 'app = FastAPI(...)'
        # Module path for uvicorn should be relative to the project root for installed packages
        uvicorn.run(
            "pravah.app.main:app",
            host=current_host,
            port=current_port,
            log_level=settings.log_level.lower(),
            reload=current_reload,
            factory=True # Use factory=True if app is created inside a function in main.py
        )
    except Exception as e:
        typer.secho(f"Error starting FastAPI server: {e}", fg=typer.colors.RED)
        logger.error(f"Error starting FastAPI server: {e}", exc_info=True)
        raise typer.Exit(code=1)

@app.command("version")
def show_version():
    """
    Displays the current version of Pravah.
    """
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            pravah_version = version("pravah") # Reads version from pyproject.toml
        except PackageNotFoundError:
            pravah_version = "Unknown (Pravah not installed as package or in editable mode)"
        typer.echo(f"Pravah Version: {pravah_version}")
        typer.echo(f"Python Version: {sys.version.split(' ')[0]}")
    except ImportError:
        typer.secho("Python 3.8+ required for version lookup. Cannot determine Pravah version.", fg=typer.colors.YELLOW)
        typer.echo(f"Python Version: {sys.version.split(' ')[0]}")
    except Exception as e:
        typer.secho(f"An unexpected error occurred while getting version: {e}", fg=typer.colors.RED)
        logger.error(f"Error getting version: {e}", exc_info=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()