import pytest
from PySide6.QtCore import Qt

# Import the custom widget(s) to be tested
from src.sanchay_app.ui.widgets.progress_bar import SanchayProgressBar


def test_sanchay_progress_bar_initialization(qtbot):
    """
    Tests if SanchayProgressBar initializes with correct default values.
    """
    progress_bar = SanchayProgressBar()
    qtbot.addWidget(progress_bar)  # Ensures the widget is properly managed by Qt's event loop

    assert progress_bar.value() == 0
    assert progress_bar.minimum() == 0
    assert progress_bar.maximum() == 100
    assert progress_bar.alignment() == Qt.AlignCenter
    assert progress_bar.isTextVisible() is True
    assert progress_bar.format() == "%p%"


def test_sanchay_progress_bar_value_setting(qtbot):
    """
    Tests setting the value of the SanchayProgressBar.
    """
    progress_bar = SanchayProgressBar()
    qtbot.addWidget(progress_bar)

    progress_bar.setValue(50)
    assert progress_bar.value() == 50

    progress_bar.setValue(100)
    assert progress_bar.value() == 100

    progress_bar.setValue(0)
    assert progress_bar.value() == 0


def test_sanchay_progress_bar_value_clamping(qtbot):
    """
    Tests if the value of SanchayProgressBar is correctly clamped within min/max bounds.
    """
    progress_bar = SanchayProgressBar()
    qtbot.addWidget(progress_bar)

    # Test clamping below minimum
    progress_bar.setValue(-10)
    assert progress_bar.value() == progress_bar.minimum()

    # Test clamping above maximum
    progress_bar.setValue(150)
    assert progress_bar.value() == progress_bar.maximum()

    # Change min/max and re-test clamping
    progress_bar.setMinimum(10)
    progress_bar.setMaximum(90)

    progress_bar.setValue(5)  # Below new minimum
    assert progress_bar.value() == 10

    progress_bar.setValue(95)  # Above new maximum
    assert progress_bar.value() == 90


def test_sanchay_progress_bar_min_max_setting(qtbot):
    """
    Tests setting minimum and maximum values for SanchayProgressBar.
    """
    progress_bar = SanchayProgressBar()
    qtbot.addWidget(progress_bar)

    new_min = 10
    new_max = 200
    progress_bar.setMinimum(new_min)
    progress_bar.setMaximum(new_max)

    assert progress_bar.minimum() == new_min
    assert progress_bar.maximum() == new_max

    # Ensure current value adjusts if it's out of new bounds after min/max change
    progress_bar.setValue(5)  # Will be clamped to new_min (10)
    assert progress_bar.value() == new_min

    progress_bar.setValue(250)  # Will be clamped to new_max (200)
    assert progress_bar.value() == new_max


def test_sanchay_progress_bar_text_visibility(qtbot):
    """
    Tests setting text visibility for SanchayProgressBar.
    """
    progress_bar = SanchayProgressBar()
    qtbot.addWidget(progress_bar)

    progress_bar.setTextVisible(False)
    assert progress_bar.isTextVisible() is False

    progress_bar.setTextVisible(True)
    assert progress_bar.isTextVisible() is True


def test_sanchay_progress_bar_format_setting(qtbot):
    """
    Tests setting the format string for SanchayProgressBar.
    """
    progress_bar = SanchayProgressBar()
    qtbot.addWidget(progress_bar)

    custom_format = "Processing: %v / %m items"
    progress_bar.setFormat(custom_format)
    assert progress_bar.format() == custom_format

    # For verifying the *rendered* text (e.g., "Processing: 30 / 100 items"),
    # more involved tests involving rendering or accessibility properties would be needed.
    # Unit tests typically focus on verifying the internal state and properties.