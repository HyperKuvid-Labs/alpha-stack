import os
import sys
import time
import pyfiglet
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.table import Table
from rich.spinner import Spinner
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PromptStyle

from .config import get_api_key, set_api_key

# Initialize Rich Console
console = Console()

# Stranger Things Color Palette (adjusted)
STRANGER_RED = "#E40066"   # Neon magenta
STRANGER_ACCENT = "#FFD1DC"  # Soft pink highlight
DARK_BG = "#050315"        # Deep midnight purple

def display_logo():
    """Displays the ALPHASTACK logo in Stranger Things style."""
    term_width = console.size.width

    # Use 'slant' font - clean and always readable
    f = pyfiglet.Figlet(font="slant")
    logo_text = f.renderText("ALPHASTACK")

    styled_logo = Text(logo_text, style=f"bold {STRANGER_RED}")

    # Calculate panel width based on the actual logo width
    logo_lines = logo_text.splitlines()
    max_logo_width = max(len(line) for line in logo_lines) if logo_lines else 60
    panel_width = min(term_width - 4, max_logo_width + 10)

    panel = Panel(
        Align.center(styled_logo),
        border_style=STRANGER_RED,
        padding=(1, 2),
        width=panel_width,
        title="[bold white]PROJECT GENERATOR[/]",
        subtitle="[dim white]v0.1.0[/]",
    )
    console.print(Align.center(panel))

def setup_api_key():
    """Interactive setup for the Prime Intellect API key."""
    console.print(f"[{STRANGER_RED}]INITIALIZATION REQUIRED[/{STRANGER_RED}]")
    console.print("[dim]Enter your Prime Intellect API Key to unlock the generator.[/dim]\n")

    style = PromptStyle.from_dict({
        'prompt': '#ff0000 bold',
        'input': '#ffffff',
    })

    while True:
        api_key = prompt(
            [('class:prompt', 'API Key > ')],
            style=style,
            is_password=True
        ).strip()

        if api_key:
            if set_api_key(api_key):
                console.print(f"\n[bold green]✅ API Key securely stored.[/bold green]")
                time.sleep(1)
                return
            else:
                console.print(f"\n[bold red]❌ Failed to save configuration.[/bold red]")
                return
        else:
            console.print("[red]API Key cannot be empty.[/red]")

def get_user_input():
    """Gets project details from the user with history support."""

    console.print(f"[{STRANGER_RED}]Welcome to the Upside Down of Code Generation...[/{STRANGER_RED}]")
    console.print("[dim]Type your request below. Use [bold]Up/Down[/bold] arrows for history.[/dim]")

    existing_key = get_api_key()
    if existing_key:
        change_style = PromptStyle.from_dict({'prompt': '#ff0000 bold', 'input': '#ffffff'})
        change = prompt(
            [('class:prompt', 'Update API key? (y/N) > ')],
            style=change_style
        ).strip().lower()
        if change == 'y':
            setup_api_key()
    else:
        setup_api_key()

    # History file location
    history_file = os.path.expanduser("~/.alphastack_history")

    # Custom style for prompt_toolkit
    style = PromptStyle.from_dict({
        'prompt': '#ff0000 bold',
        'input': '#ffffff',
    })



    # Project Prompt
    console.print(Panel("[bold]What should we build?[/bold]", border_style=STRANGER_RED))
    user_prompt = prompt(
        [('class:prompt', '> ')],
        history=FileHistory(history_file),
        style=style
    ).strip()

    if not user_prompt:
        console.print(f"[bold red]❌ A vision is required to proceed.[/bold red]")
        sys.exit(1)

    # Output Directory - Mandatory Loop

    while True:
        console.print(f"[bold]Where should it manifest?[/bold] [dim](absolute path required)[/dim]")
        output_dir = prompt(
            [('class:prompt', '> ')],
            history=FileHistory(history_file + "_dirs"),
            style=style
        ).strip()

        if output_dir:
            break
        else:
            console.print("[red]Output directory cannot be empty.[/red]")

    return user_prompt, output_dir

class StatusDisplay:
    """Context manager for displaying a live status with sections."""
    def __init__(self, title="Simmering..."):
        self.title = title
        self.messages = []
        self.current_phase = "Initializing..."
        self.completed_phases = set()
        self.layout = Layout()
        self.live = None
        self.spinner = Spinner("dots", style=STRANGER_RED)

    def generate_layout(self):
        """Generates the dynamic layout table."""

        # Main Table
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)

        # Header
        header = Text("ALPHASTACK WORKING...", style=f"bold {STRANGER_RED}")

        # Phase Section with Spinner
        phase_table = Table.grid(expand=True)
        phase_table.add_column(width=3)
        phase_table.add_column(ratio=1)
        phase_table.add_row(self.spinner, Text(self.current_phase, style="bold white"))

        phase_panel = Panel(
            phase_table,
            border_style="dim white",
            title="[cyan]Current Phase[/cyan]",
            padding=(0, 1)
        )

        # Log Section
        if not self.messages:
            log_rows = ["[dim]Waiting for updates...[/dim]"]
        else:
            recent = self.messages[-8:]
            log_rows = [row for row in recent]

        log_table = Table.grid()
        log_table.add_column(justify="left", ratio=1, style="white")
        for row in log_rows:
            log_table.add_row(row)

        log_panel = Panel(
            log_table,
            border_style=STRANGER_RED,
            title="[white]Progress Log[/white]",
            padding=(0, 1),
            height=12
        )

        term_width = console.size.width
        panel_width = max(60, term_width - 6)

        # Combine
        grid.add_row(header)
        grid.add_row(phase_panel)
        grid.add_row(log_panel)

        centered_panel = Align.center(
            Panel(grid, border_style=STRANGER_RED, padding=(1, 2), width=panel_width),
            vertical="middle"
        )
        layout = Layout()
        layout.update(centered_panel)
        return layout

    def _mark_current_phase_complete(self):
        if (
            self.current_phase
            and self.current_phase not in ("Initializing...", None)
            and self.current_phase not in self.completed_phases
        ):
            self.messages.append(f"✅ {self.current_phase}")
            self.completed_phases.add(self.current_phase)

    def __enter__(self):
        self.live = Live(self.generate_layout(), refresh_per_second=10, console=console, screen=True)
        self.live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._mark_current_phase_complete()
        if self.live:
            self.live.stop()

    def update(self, message, event_type="progress"):
        """Adds a message and updates the display."""

        icon = "   "

        if event_type == "step":
            self._mark_current_phase_complete()
            self.current_phase = message
            # We don't log the new phase yet; it will appear once completed.
            icon = ""
        elif event_type == "success":
            icon = "✅ "
        elif event_type == "error":
            icon = "❌ "
        elif event_type == "warning":
            icon = "⚠️  "

        if event_type == "step":
            pass
        else:
            formatted_msg = f"{icon} {message}"
            self.messages.append(formatted_msg)

        self.live.update(self.generate_layout())

def print_success(message):
    console.print(Panel(f"[bold green]{message}[/]", border_style="green"))

def print_error(message):
    console.print(Panel(f"[bold red]{message}[/]", border_style="red"))
