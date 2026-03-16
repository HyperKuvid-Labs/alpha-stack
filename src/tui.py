import os
import sys
import time
import pyfiglet
from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
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
    """Interactive setup for the Gemini API key."""
    console.print(f"[{STRANGER_RED}]INITIALIZATION REQUIRED[/{STRANGER_RED}]")
    console.print("[dim]Enter your Gemini API Key to unlock the generator.[/dim]\n")

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

    # Problem statement language profile
    while True:
        console.print("[bold]Language profile?[/bold] [dim](cuda/others, default: others)[/dim]")
        problem_statement_language = prompt(
            [('class:prompt', '> ')],
            history=FileHistory(history_file + "_language"),
            style=style
        ).strip().lower()

        if not problem_statement_language:
            problem_statement_language = "others"

        if problem_statement_language in {"cuda", "others"}:
            break

        console.print("[red]Please choose either 'cuda' or 'others'.[/red]")

    return user_prompt, output_dir, problem_statement_language

class StatusDisplay:
    """Context manager for a clean, sequential live status display."""
    def __init__(self, title="Generating project"):
        self.title = title
        self.messages = []
        self.current_phase = "Waiting for first step..."
        self.phase_counter = 0
        self._last_completed_phase = None
        self.live = None
        self.spinner = Spinner("dots", style=STRANGER_RED)

    def generate_layout(self):
        """Build a compact view focused on current phase and ordered updates."""
        phase_table = Table.grid(expand=True)
        phase_table.add_column(width=3)
        phase_table.add_column(ratio=1)
        phase_table.add_row(self.spinner, Text(self.current_phase, style="bold white"))

        if self.messages:
            recent_lines = self.messages[-10:]
            updates_text = Text("\n".join(recent_lines), style="white")
        else:
            updates_text = Text("No updates yet...", style="dim")

        content = Group(
            Text("ALPHASTACK", style=f"bold {STRANGER_RED}"),
            Text(""),
            Text("Current", style="bold"),
            phase_table,
            Text(""),
            Text("Updates", style="bold"),
            updates_text,
        )

        return Align.center(
            Panel(content, border_style=STRANGER_RED, padding=(1, 2), width=max(70, console.size.width - 6)),
            vertical="middle"
        )

    def _mark_current_phase_complete(self):
        if self.current_phase and self.current_phase != "Waiting for first step...":
            if self.current_phase != self._last_completed_phase:
                self.messages.append(f"✓ {self.current_phase}")
                self._last_completed_phase = self.current_phase

    def __enter__(self):
        self.live = Live(self.generate_layout(), refresh_per_second=10, console=console, screen=True)
        self.live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._mark_current_phase_complete()
        if self.live:
            self.live.stop()

    def update(self, message, event_type="progress"):
        """Add a message and refresh the live display."""
        if event_type == "step":
            self._mark_current_phase_complete()
            self.phase_counter += 1
            self.current_phase = f"{self.phase_counter}. {message}"
            self.messages.append(f"→ {self.current_phase}")
        elif event_type == "success":
            self.messages.append(f"✅ {message}")
        elif event_type == "error":
            self.messages.append(f"❌ {message}")
        elif event_type == "warning":
            self.messages.append(f"⚠️  {message}")
        else:
            self.messages.append(f"• {message}")

        if self.live:
            self.live.update(self.generate_layout())

def print_success(message):
    console.print(Panel(f"[bold green]{message}[/]", border_style="green"))

def print_error(message):
    console.print(Panel(f"[bold red]{message}[/]", border_style="red"))
