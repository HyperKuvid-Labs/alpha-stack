import logging
import os
from typing import Optional, Any, Callable

from PySide6.QtCore import QSize, Signal, Slot, QThread
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QMenuBar, QToolBar, QStatusBar, QFileDialog, QMessageBox, QLabel
)

# Internal imports
from sanchay_app.config import settings
from sanchay_app.core.job_manager import JobManager
from sanchay_app.ui.threads import WorkerThread # Assuming this is implemented as discussed

# Configure logging for this module
logger = logging.getLogger(__name__)


class SanchayMainWindow(QMainWindow):
    """
    The main application window, serving as the primary container for all other UI widgets.
    It manages the overall GUI layout, including menus, toolbars, and the central content area,
    and connects user actions to the application's core logic via the JobManager.
    """

    # Signal to update the status bar message from any part of the UI or worker threads
    status_message_signal = Signal(str)

    def __init__(self, app_instance: QApplication):
        """
        Initializes the main application window.

        Args:
            app_instance: A reference to the QApplication instance, used for setting styles.
        """
        super().__init__()
        self.app_instance = app_instance

        self.setWindowTitle(settings.APP_NAME)
        # Set an initial geometry (x, y, width, height)
        self.setGeometry(100, 100, 1024, 768)

        self.job_manager: JobManager = JobManager()
        self.worker_thread: Optional[WorkerThread] = None
        self.current_selected_directory: Optional[str] = None

        self._load_styles()
        self._set_app_icon()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_central_widget()

        self._connect_signals()

        logger.info(f"{settings.APP_NAME} Main window initialized.")
        self.status_message_signal.emit("Ready")
        # Initially disable scan action until a directory is selected
        self.start_scan_action.setEnabled(False)

    def _load_styles(self) -> None:
        """Loads and applies the Qt Style Sheet for custom UI theming."""
        style_path = os.path.join(settings.ASSETS_DIR, "styles", "main.qss")
        if os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f:
                    self.app_instance.setStyleSheet(f.read())
                logger.debug(f"Loaded stylesheet from {style_path}")
            except Exception as e:
                logger.error(f"Failed to load stylesheet from {style_path}: {e}")
        else:
            logger.warning(f"Stylesheet not found at {style_path}")

    def _set_app_icon(self) -> None:
        """Sets the application window icon."""
        icon_path = os.path.join(settings.ASSETS_DIR, "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logger.debug(f"Loaded app icon from {icon_path}")
        else:
            logger.warning(f"App icon not found at {icon_path}")

    def _create_actions(self) -> None:
        """Initializes all QAction objects used in menus and toolbars."""
        # File Menu Actions
        self.open_dir_action = QAction(QIcon.fromTheme("folder-open"), "&Open Directory...", self)
        self.open_dir_action.setShortcut("Ctrl+O")
        self.open_dir_action.setStatusTip("Select a directory on the local filesystem to process")
        self.open_dir_action.triggered.connect(self.open_directory_dialog)

        self.exit_action = QAction(QIcon.fromTheme("application-exit"), "E&xit", self)
        self.exit_action.setShortcut("Alt+F4")
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

        # Processing Actions
        self.start_scan_action = QAction(QIcon.fromTheme("media-playback-start"), "&Start Scan", self)
        self.start_scan_action.setShortcut("Ctrl+S")
        self.start_scan_action.setStatusTip("Start processing files in the selected directory")
        self.start_scan_action.triggered.connect(self.start_processing_job)

        # Help Menu Actions
        self.about_action = QAction("&About Sanchay", self)
        self.about_action.setStatusTip(f"Show information about {settings.APP_NAME}")
        self.about_action.triggered.connect(self.show_about_dialog)

    def _create_menus(self) -> None:
        """Creates the application's menu bar and populates it with actions."""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.open_dir_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        process_menu = menu_bar.addMenu("&Process")
        process_menu.addAction(self.start_scan_action)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self) -> None:
        """Creates the main toolbar and adds common actions."""
        main_toolbar = self.addToolBar("Main Toolbar")
        main_toolbar.setIconSize(QSize(32, 32))
        main_toolbar.addAction(self.open_dir_action)
        main_toolbar.addAction(self.start_scan_action)

    def _create_status_bar(self) -> None:
        """Creates and initializes the application's status bar."""
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Application Ready")

    def _create_central_widget(self) -> None:
        """
        Creates the central widget for the main window.
        This widget will house the dynamic content of the application.
        """
        central_widget = QWidget()
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # A simple QLabel for displaying information and results for MVP
        self.info_label = QLabel("Welcome to Sanchay!\nSelect a directory and click 'Start Scan' to begin processing.")
        self.info_label.setWordWrap(True)
        self.main_layout.addWidget(self.info_label)

        # Future: Integrate more complex widgets here, e.g., a JobProgressWidget
        # from sanchay_app.ui.widgets.job_progress_widget import JobProgressWidget
        # self.job_progress_widget = JobProgressWidget()
        # self.main_layout.addWidget(self.job_progress_widget)

        self.setCentralWidget(central_widget)

    def _connect_signals(self) -> None:
        """Connects internal signals to their respective slots."""
        self.status_message_signal.connect(self.statusBar().showMessage)
        # Further connections to job_manager signals would go here if JobManager
        # were designed to emit Qt signals directly, but we're using WorkerThread
        # to encapsulate its execution and relay progress.

    @Slot()
    def open_directory_dialog(self) -> None:
        """
        Opens a directory selection dialog and updates the UI with the selected path.
        """
        # Get the initial directory from settings or fall back to current working directory
        initial_dir = self.current_selected_directory or os.getcwd()
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory to Process", initial_dir
        )
        if directory:
            logger.info(f"Directory selected: {directory}")
            self.current_selected_directory = directory
            self.status_message_signal.emit(f"Directory selected: {directory}")
            self.info_label.setText(f"Selected: <b>{directory}</b><br>Click 'Start Scan' to process.")
            self.start_scan_action.setEnabled(True)  # Enable scan button
        else:
            self.status_message_signal.emit("Directory selection cancelled.")
            logger.debug("Directory selection cancelled.")
            # If no directory is selected after a previous one was, keep scan action enabled
            # If no directory was ever selected, keep it disabled
            if not self.current_selected_directory:
                self.start_scan_action.setEnabled(False)

    @Slot()
    def start_processing_job(self) -> None:
        """
        Initiates a new file processing job in a separate worker thread.
        """
        if not self.current_selected_directory:
            QMessageBox.warning(self, "No Directory Selected", "Please select a directory to process first.")
            return

        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.information(self, "Job in Progress", "A processing job is already running.")
            return

        self.status_message_signal.emit(f"Starting scan for: {self.current_selected_directory}...")
        logger.info(f"Initiating processing job for directory: {self.current_selected_directory}")
        self.info_label.setText(f"Scanning <b>'{self.current_selected_directory}'</b>...<br>(This might take a while)")

        # Create and start a worker thread. The WorkerThread will call the job_manager's method.
        self.worker_thread = WorkerThread(
            job_func=self.job_manager.start_directory_scan,
            # The WorkerThread is designed to append a 'progress_callback' to these args
            args=(self.current_selected_directory,)
        )

        # Connect signals from the worker thread to main window slots
        self.worker_thread.started.connect(
            lambda: self.status_message_signal.emit("Processing started in background...")
        )
        self.worker_thread.finished.connect(self._handle_job_finished)
        self.worker_thread.progress_update.connect(self._handle_job_progress)
        self.worker_thread.error_occurred.connect(self._handle_job_error)

        # Disable UI elements that could interfere with the running job
        self.start_scan_action.setEnabled(False)
        self.open_dir_action.setEnabled(False)

        self.worker_thread.start()

    @Slot(str)
    def _handle_job_progress(self, message: str) -> None:
        """
        Updates the status bar and potentially other UI elements with job progress.

        Args:
            message: The progress message string.
        """
        self.status_message_signal.emit(message)
        logger.debug(f"Job progress update: {message}")
        # Future: self.job_progress_widget.update_progress_text(message)

    @Slot(bool, str, object)
    def _handle_job_finished(self, success: bool, message: str, result: Optional[Any]) -> None:
        """
        Handles the completion of a processing job (success or failure).

        Args:
            success: True if the job completed successfully, False otherwise.
            message: A descriptive message about the job outcome.
            result: The final result object returned by the job function, if any.
        """
        self.status_message_signal.emit(message)
        self.start_scan_action.setEnabled(True)  # Re-enable actions
        self.open_dir_action.setEnabled(True)
        self.worker_thread = None  # Clear the worker thread reference

        if success:
            logger.info(f"Processing job completed successfully: {message}")
            self.info_label.setText(f"Scan finished! <br><b>{message}</b><br><br>Results: {result}")
            QMessageBox.information(self, "Scan Complete", f"Directory scan finished successfully!\n{message}")
        else:
            logger.error(f"Processing job failed: {message}")
            self.info_label.setText(f"Scan failed: <b>{message}</b>")
            QMessageBox.critical(self, "Scan Failed", f"An error occurred during scan:\n{message}")

    @Slot(str)
    def _handle_job_error(self, error_message: str) -> None:
        """
        Handles an error specifically emitted by the worker thread.

        Args:
            error_message: The error message string.
        """
        self.status_message_signal.emit(f"Error: {error_message}")
        logger.error(f"Job encountered an error: {error_message}")
        # Error handling is also covered by _handle_job_finished(False, ...),
        # but this slot can catch specific `error_occurred` signals for immediate feedback.
        self.start_scan_action.setEnabled(True)
        self.open_dir_action.setEnabled(True)
        self.worker_thread = None
        QMessageBox.critical(self, "Error During Scan", f"An unexpected error occurred:\n{error_message}")

    @Slot()
    def show_about_dialog(self) -> None:
        """Displays the 'About' dialog for the application."""
        QMessageBox.about(
            self,
            f"About {settings.APP_NAME}",
            f"<b>{settings.APP_NAME}</b> v{settings.APP_VERSION}<br><br>"
            "A powerful tool for file and data collection and processing.<br><br>"
            "Built with Python (PySide6) and Rust.<br>"
            "&copy; 2023 Project Sanchay Team"
        )

    def closeEvent(self, event: Any) -> None:
        """
        Handles the application's close event, prompting the user for confirmation
        and attempting to stop any running worker threads gracefully.
        """
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "A processing job is currently running. Exiting now will cancel it. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
        else:
            reply = QMessageBox.question(
                self, "Confirm Exit", "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

        if reply == QMessageBox.StandardButton.Yes:
            if self.worker_thread and self.worker_thread.isRunning():
                logger.warning("Application closing while worker thread is running. Requesting interruption.")
                self.worker_thread.requestInterruption()
                if not self.worker_thread.wait(5000):  # Wait up to 5 seconds for thread to finish
                    logger.error("Worker thread did not terminate gracefully. Forcing quit.")
                    self.worker_thread.terminate()
            logger.info("Application exiting.")
            event.accept()
        else:
            event.ignore()