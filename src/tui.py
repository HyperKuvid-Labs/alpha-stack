import os
import sys
import time

import pyfiglet
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PromptStyle
from rich.align import Align
from rich.console import Console
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from .config import get_api_key, set_api_key

# Initialize Rich Console
console = Console()

# Neon Noir Palette
NEON_PRIMARY = "#FF2E88"
NEON_ACCENT = "#FFB3D9"
NEON_INFO = "#7EE7FF"
NEON_SUCCESS = "#5CFFB5"
NEON_WARNING = "#FFD166"
NEON_ERROR = "#FF6B81"
NEON_MUTED = "#9AA4BF"

PROMPT_STYLE = PromptStyle.from_dict(
    {
        "prompt": f"{NEON_PRIMARY} bold",
        "input": "#ffffff",
    }
)


def _styled_input(label, history_path=None, is_password=False):
    history = FileHistory(history_path) if history_path else None
    return prompt(
        [("class:prompt", f"{label} ")],
        history=history,
        style=PROMPT_STYLE,
        is_password=is_password,
    ).strip()


def _section_panel(title, subtitle=None):
    body = Text(title, style="bold white")
    if subtitle:
        body.append(f"\n{subtitle}", style=NEON_MUTED)
    return Panel(body, border_style=NEON_PRIMARY, padding=(0, 2))


def display_logo():
    """Displays the ALPHASTACK logo with a modern neon aesthetic."""
    term_width = console.size.width

    try:
        logo_text = pyfiglet.Figlet(font="slant").renderText("ALPHASTACK")
    except Exception:
        logo_text = "ALPHASTACK"

    styled_logo = Text(logo_text, style=f"bold {NEON_PRIMARY}")
    strapline = Text("Build. Validate. Ship.", style=f"bold {NEON_INFO}")

    logo_lines = logo_text.splitlines()
    max_logo_width = max(len(line) for line in logo_lines) if logo_lines else 60
    panel_width = min(term_width - 4, max_logo_width + 14)

    content = Group(
        Align.center(styled_logo),
        Align.center(Text("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", style=NEON_MUTED)),
        Align.center(strapline),
    )

    panel = Panel(
        content,
        border_style=NEON_PRIMARY,
        padding=(1, 2),
        width=panel_width,
        title="[bold white] ALPHASTACK PROJECT GENERATOR [/bold white]",
        subtitle=f"[bold {NEON_MUTED}]v0.1.0[/bold {NEON_MUTED}]",
    )
    console.print(Align.center(panel))
    console.print(Align.center(Text("Neon pipeline for code generation", style=NEON_MUTED)))
    console.print()


def setup_api_key():
    """Interactive setup for the Gemini API key."""
    console.print(_section_panel("API Key Setup", "Enter your Gemini key to activate generation."))

    while True:
        api_key = _styled_input("API Key >", is_password=True)

        if api_key:
            if set_api_key(api_key):
                console.print(f"\n[bold {NEON_SUCCESS}]✓ API Key securely stored.[/bold {NEON_SUCCESS}]")
                time.sleep(0.6)
                return

            console.print(f"\n[bold {NEON_ERROR}]✗ Failed to save configuration.[/bold {NEON_ERROR}]")
            return

        console.print(f"[{NEON_ERROR}]API Key cannot be empty.[/{NEON_ERROR}]")


def get_user_input():
    """Gets project details from the user with history support."""
    console.print(Rule(style=NEON_PRIMARY))
    console.print(Align.center(Text("MISSION CONTROL", style=f"bold {NEON_PRIMARY}")))
    console.print(Align.center(Text("Use ↑/↓ for history. Keep prompts concise and specific.", style=NEON_MUTED)))
    console.print(Rule(style=NEON_PRIMARY))

    existing_key = get_api_key()
    if existing_key:
        change = _styled_input("Update API key? (y/N) >").lower()
        if change == "y":
            setup_api_key()
    else:
        setup_api_key()

    history_file = os.path.expanduser("~/.alphastack_history")

    console.print(_section_panel("What should we build?", "Describe the product, stack, and constraints."))
    user_prompt = _styled_input(">", history_path=history_file)

    if not user_prompt:
        console.print(f"[bold {NEON_ERROR}]✗ A vision is required to proceed.[/bold {NEON_ERROR}]")
        sys.exit(1)

    while True:
        console.print(_section_panel("Where should it manifest?", "Absolute path required."))
        output_dir = _styled_input(">", history_path=history_file + "_dirs")

        if output_dir:
            break

        console.print(f"[{NEON_ERROR}]Output directory cannot be empty.[/{NEON_ERROR}]")

    profile_table = Table.grid(padding=(0, 2))
    profile_table.add_column(style=f"bold {NEON_ACCENT}", width=10)
    profile_table.add_column(style=NEON_MUTED)
    profile_table.add_row("cuda", "Optimized for CUDA/C++ style prompts")
    profile_table.add_row("others", "General-purpose language profile")

    console.print(
        Panel(
            Group(
                Text("Select problem statement profile", style="bold white"),
                Text(""),
                profile_table,
            ),
            border_style=NEON_PRIMARY,
            padding=(0, 2),
        )
    )

    while True:
        problem_statement_language = _styled_input(
            "Profile (cuda/others, default: others) >",
            history_path=history_file + "_language",
        ).lower()

        if not problem_statement_language:
            problem_statement_language = "others"

        if problem_statement_language in {"cuda", "others"}:
            break

        console.print(f"[{NEON_WARNING}]Please choose either 'cuda' or 'others'.[/{NEON_WARNING}]")

    console.print()
    console.print(Align.center(Text("Configuration locked. Spinning up generation...", style=NEON_INFO)))
    return user_prompt, output_dir, problem_statement_language


class StatusDisplay:
    """Context manager for a polished, sequential live status dashboard."""

    def __init__(self, title="Generating project"):
        self.title = title
        self.messages = []
        self.current_phase = "Preparing pipeline..."
        self.phase_counter = 0
        self._last_completed_phase = None
        self.live = None
        self.spinner = Spinner("dots", style=NEON_PRIMARY)
        self.started_at = time.time()
        self.stats = {"success": 0, "warning": 0, "error": 0, "progress": 0}

    def _elapsed(self):
        elapsed = int(time.time() - self.started_at)
        mins, secs = divmod(elapsed, 60)
        return f"{mins:02d}:{secs:02d}"

    def _header(self):
        title = Text(self.title, style=f"bold {NEON_PRIMARY}")
        title.append("  •  ", style=NEON_MUTED)
        title.append(f"elapsed {self._elapsed()}", style=NEON_INFO)
        return title

    def _stats_line(self):
        stats = Text()
        stats.append(f"✓ {self.stats['success']}  ", style=NEON_SUCCESS)
        stats.append(f"⚠ {self.stats['warning']}  ", style=NEON_WARNING)
        stats.append(f"✗ {self.stats['error']}  ", style=NEON_ERROR)
        stats.append(f"• {self.stats['progress']}", style=NEON_MUTED)
        return stats

    def generate_layout(self):
        """Build a compact, high-signal dashboard with current phase and feed."""
        phase_table = Table.grid(expand=True)
        phase_table.add_column(width=3)
        phase_table.add_column(ratio=1)
        phase_table.add_row(self.spinner, Text(self.current_phase, style=f"bold {NEON_ACCENT}"))

        if self.messages:
            recent_lines = self.messages[-8:]
            updates_text = Text("\n".join(recent_lines), style="white")
        else:
            updates_text = Text("No updates yet...", style=NEON_MUTED)

        content = Group(
            self._header(),
            Text(""),
            Text("Current Phase", style="bold white"),
            phase_table,
            Text(""),
            Text("Activity Feed", style="bold white"),
            updates_text,
            Text(""),
            self._stats_line(),
        )

        return Align.center(
            Panel(
                content,
                border_style=NEON_PRIMARY,
                padding=(1, 2),
                width=max(76, console.size.width - 6),
                title="[bold white] PIPELINE STATUS [/bold white]",
            ),
            vertical="middle",
        )

    def _mark_current_phase_complete(self):
        if self.current_phase and self.current_phase != "Preparing pipeline...":
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
            self.stats["progress"] += 1
        elif event_type == "success":
            self.messages.append(f"✅ {message}")
            self.stats["success"] += 1
        elif event_type == "error":
            self.messages.append(f"❌ {message}")
            self.stats["error"] += 1
        elif event_type == "warning":
            self.messages.append(f"⚠️  {message}")
            self.stats["warning"] += 1
        else:
            self.messages.append(f"• {message}")
            self.stats["progress"] += 1

        if self.live:
            self.live.update(self.generate_layout())


def print_success(message):
    console.print(Panel(f"[bold {NEON_SUCCESS}]✓ {message}[/bold {NEON_SUCCESS}]", border_style=NEON_SUCCESS))


def print_error(message):
    console.print(Panel(f"[bold {NEON_ERROR}]✗ {message}[/bold {NEON_ERROR}]", border_style=NEON_ERROR))
