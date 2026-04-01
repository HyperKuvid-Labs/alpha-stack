import pytest
from calc.ui import TermCalcApp
from textual.widgets import Input, Button

@pytest.mark.asyncio
async def test_app_rendering():
    """Test that the application renders correctly."""
    app = TermCalcApp()
    async with app.run_test() as pilot:
        # Check that the main input widget exists
        assert app.query_one(Input)
        # Verify initial focus or state if applicable
        assert app.focused is not None

@pytest.mark.asyncio
async def test_input_submission():
    """Test that typing into the input works as expected."""
    app = TermCalcApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        await pilot.click("#btn-1")
        await pilot.click("#btn-add")
        await pilot.click("#btn-2")
        await pilot.click("#btn-eq")
        
        # Verify the input has been processed
        # The engine should calculate 1+2 = 3.0, UI converter makes it 3
        assert input_widget.value == "3"

@pytest.mark.asyncio
async def test_button_interaction():
    """Test that clicking a button triggers an action."""
    app = TermCalcApp()
    async with app.run_test() as pilot:
        # Click a button
        await pilot.click("#btn-7")
        input_widget = app.query_one(Input)
        assert input_widget.value == "7"

@pytest.mark.asyncio
async def test_update_cycle():
    """Test that the TUI responds to state changes."""
    app = TermCalcApp()
    async with app.run_test() as pilot:
        # Simulate interaction
        await pilot.click("#btn-5")
        await pilot.click("#btn-mul")
        await pilot.click("#btn-5")
        await pilot.click("#btn-eq")
        
        input_widget = app.query_one(Input)
        assert input_widget.value == "25"
