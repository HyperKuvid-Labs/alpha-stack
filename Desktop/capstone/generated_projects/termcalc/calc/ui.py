from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.widgets import Button, Input, Static
from calc.engine import CalculatorEngine

class TermCalcApp(App):
    CSS = """
    Screen {
        align: center middle;
    }
    #calculator {
        width: 40;
        height: auto;
        border: solid green;
    }
    #display {
        margin: 1;
    }
    #buttons {
        grid-size: 4;
        grid-gutter: 1 2;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Input(id="display", placeholder="Enter expression..."),
            Grid(
                Button("7", id="btn-7"), Button("8", id="btn-8"), Button("9", id="btn-9"), Button("/", id="btn-div"),
                Button("4", id="btn-4"), Button("5", id="btn-5"), Button("6", id="btn-6"), Button("*", id="btn-mul"),
                Button("1", id="btn-1"), Button("2", id="btn-2"), Button("3", id="btn-3"), Button("-", id="btn-sub"),
                Button("0", id="btn-0"), Button(".", id="btn-dot"), Button("=", id="btn-eq"), Button("+", id="btn-add"),
                id="buttons"
            ),
            id="calculator"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        display = self.query_one("#display", Input)
        button_id = event.button.id

        if button_id == "btn-eq":
            try:
                result = CalculatorEngine.calculate(display.value)
                display.value = str(int(result) if isinstance(result, float) and result.is_integer() else result)
            except Exception as e:
                display.value = f"Error: {e}"
        else:
            # Simple mapping for buttons to input
            mapping = {
                "btn-0": "0", "btn-1": "1", "btn-2": "2", "btn-3": "3",
                "btn-4": "4", "btn-5": "5", "btn-6": "6", "btn-7": "7",
                "btn-8": "8", "btn-9": "9", "btn-dot": ".",
                "btn-div": "/", "btn-mul": "*", "btn-sub": "-", "btn-add": "+"
            }
            if button_id in mapping:
                display.value += mapping[button_id]

if __name__ == "__main__":
    TermCalcApp().run()
