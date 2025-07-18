from celery import Celery
from karyaksham_api.core.config import settings

celery_app = Celery(
    "karyaksham_worker",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    include=["karyaksham_workers.tasks.processing"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # Optional: Configure task routing or queues if needed for more complex scenarios
    # task_routes = {
    #     'karyaksham_workers.tasks.processing.process_file': {'queue': 'file_processing_queue'},
    # },
)

# Optional: Add a signal handler for when the app is ready (e.g., for custom logging setup)
# from celery.signals import worker_ready
#
# @worker_ready.connect
# def setup_logging(sender, **kwargs):
#     # You could configure your structured logging here, e.g., using loguru or standard logging
#     # For now, Celery's default logging is usually sufficient for basic debugging
#     pass

if __name__ == "__main__":
    # This block is for direct execution of the script for testing/debugging purposes
    # In production, Celery workers are typically started via the 'celery -A' command
    celery_app.start()