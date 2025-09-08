```python
from PySide6.QtWidgets import QProgressBar
from PySide6.QtCore import Qt

class SanchayProgressBar(QProgressBar):
    """
    A custom QProgressBar widget for Project Sanchay, designed to provide
    visual feedback for long-running operations.

    It dynamically adapts its display format to show percentage, current/total
    counts, and a custom status message. It supports both determinate (known total)
    and indeterminate (unknown total) progress states.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sanchayProgressBar") # For potential QSS styling from main.qss
        self.setTextVisible(True) # Ensure text is always visible within the bar
        self._status_message = ""
        self.reset_progress() # Initialize to a default state

    def _update_format_string(self):
        """
        Internal helper to update the progress bar's format string based on
        its current state (determinate vs. indeterminate) and status message.
        """
        if self.maximum() > 0: # Determinate mode (min and max are distinct)
            # Special case for the initial 'Ready' state after a reset
            if self.value() == self.minimum() and not self._status_message and self.maximum() == 100:
                self.setFormat("Ready")
            else:
                # %p: percentage, %v: current value (processed items), %m: maximum value (total items)
                format_parts = ["%p%", "%v/%m"]
                if self._status_message:
                    format_parts.append(self._status_message)
                self.setFormat(" - ".join(format_parts))
        else: # Indeterminate mode (min == max == 0)
            self.setFormat(self._status_message if self._status_message else "Processing...")

    def set_task_range(self, total_items: int):
        """
        Sets the total number of items for the progress bar to track.
        Switches to determinate mode if `total_items` is greater than 0.
        If `total_items` is 0 or less, it will switch to an indeterminate state.
        Clears any existing status message for the new task.
        """
        self._status_message = "" # Clear previous message for a new task
        if total_items > 0:
            self.setRange(0, total_items)
            self.setValue(0)
        else:
            self.set_indeterminate("Initializing task...")
        self._update_format_string()

    def update_progress(self, processed_count: int, message: str = ""):
        """
        Updates the progress bar with the current count of processed items
        and an optional status message. This method should be called repeatedly
        during the progress of a task.
        
        If the bar is in an indeterminate state (`maximum() == 0`) and
        `processed_count` becomes positive, it will remain indeterminate but its
        status message will be updated. It's expected that `set_task_range`
        is called if a determinate task with a known total is intended.
        """
        self.setValue(processed_count) # QProgressBar handles clipping to its current range
        if message:
            self._status_message = message
        self._update_format_string()

    def set_status_message(self, message: str):
        """
        Sets a custom status message to display alongside the progress.
        This updates the text without changing the numerical progress.
        """
        self._status_message = message
        self._update_format_string()

    def set_indeterminate(self, message: str = "Processing..."):
        """
        Sets the progress bar to an indeterminate (busy) state.
        This is suitable for tasks where the total progress is unknown.
        """
        self.setRange(0, 0) # Set min and max to 0 for indeterminate mode
        self.setValue(0) # Value is ignored in indeterminate mode, but set for consistency
        self._status_message = message
        self._update_format_string()

    def reset_progress(self):
        """
        Resets the progress bar to its initial state, showing "Ready".
        It transitions to a determinate mode with a range of 0-100, and clears
        the internal status message. `_update_format_string` then identifies
        this as the "Ready" state and displays accordingly.
        """
        self.setRange(0, 100) # Default range for a "clean" determinate state
        self.setValue(0)
        self._status_message = "" # Clear any previous message
        self._update_format_string() # This will now correctly show "Ready"
```