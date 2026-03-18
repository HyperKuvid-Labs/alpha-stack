import os
import sys
import time
import json
import io
import traceback
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PromptStyle
from rich.console import Console
from rich.text import Text

from .config import get_api_key, set_api_key

# Initialize Rich Console
console = Console(file=sys.__stdout__)

# Tokyo Night Palette (using original Neon Noir variable names)

NEON_PRIMARY  = "#BB9AF7"    # Signature Tokyo Night purple – vibrant accent / main highlight
NEON_ACCENT   = "#C0CAF5"    # Soft periwinkle / light foreground blue-purple
NEON_INFO     = "#7AA2F7"    # Bright info/link blue
NEON_SUCCESS  = "#9ECE6A"    # Fresh neon green for success/positive
NEON_WARNING  = "#E0AF68"    # Warm amber/gold for warnings
NEON_ERROR    = "#F7768E"    # Vivid coral-red / error pinkish-red
NEON_MUTED    = "#565F89"    # Cool muted indigo-gray (perfect for secondary/quiet text)

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


def _load_provider_options():
    config_path = Path(__file__).with_name("providers.json")
    fallback_options = ["google", "openai", "vllm", "openrouter", "prime_intellect"]
    fallback_default = "google"

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        model_providers = config.get("model_providers", {})
        provider_options = [
            name.strip().lower()
            for name in model_providers.keys()
            if isinstance(name, str) and name.strip()
        ]

        if not provider_options:
            return fallback_options, fallback_default

        default_provider = str(config.get("default_provider", "")).strip().lower()
        if default_provider not in provider_options:
            default_provider = provider_options[0]

        return provider_options, default_provider
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return fallback_options, fallback_default


def display_logo():
    """Display a minimal Claude-like startup header."""
    console.print(Text("alphastack", style=f"bold {NEON_PRIMARY}"))
    console.print(Text("Project generator • Build. Validate. Ship.", style=NEON_MUTED))
    console.print()


def setup_api_key():
    """Interactive setup for the Gemini API key."""
    console.print(Text("Set API key", style=f"bold {NEON_ACCENT}"))
    console.print(Text("Enter your key to continue.", style=NEON_MUTED))

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
    console.print(Text("Describe what to build. Use ↑/↓ for history.", style=NEON_MUTED))
    console.print()

    provider_options, default_provider = _load_provider_options()
    provider_options_text = "/".join(provider_options)

    # ask for the provider before api key step
    while True:
        provider_input = _styled_input(
            f"Select provider ({provider_options_text}) [{default_provider}] >"
        ).lower()
        provider = provider_input or default_provider
        if provider in provider_options:
            break
        console.print(
            f"[{NEON_WARNING}]Please choose one of: {provider_options_text}.[/{NEON_WARNING}]"
        )

    if provider in {"google", "openai", "openrouter", "prime_intellect"}:
        existing_key = get_api_key()
        if existing_key:
            change = _styled_input("Update API key? (y/N) >").lower()
            if change == "y":
                setup_api_key()
        else:
            setup_api_key()
    else:
        console.print(
            f"[{NEON_MUTED}]Provider '{provider}' selected.[/{NEON_MUTED}]"
        )

    history_file = os.path.expanduser("~/.alphastack_history")

    console.print(Text("Prompt", style=f"bold {NEON_ACCENT}"))
    user_prompt = _styled_input(">", history_path=history_file)

    if not user_prompt:
        console.print(f"[bold {NEON_ERROR}]✗ A vision is required to proceed.[/bold {NEON_ERROR}]")
        sys.exit(1)

    while True:
        console.print(Text("Output directory (absolute path)", style=f"bold {NEON_ACCENT}"))
        output_dir = _styled_input(">", history_path=history_file + "_dirs")

        if output_dir:
            break

        console.print(f"[{NEON_ERROR}]Output directory cannot be empty.[/{NEON_ERROR}]")

    console.print(Text("Profile", style=f"bold {NEON_ACCENT}"))
    console.print(Text("- cuda: CUDA/C++ optimized", style=NEON_MUTED))
    console.print(Text("- others: general purpose", style=NEON_MUTED))

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
    console.print(Text("Configuration locked. Starting generation...", style=NEON_INFO))
    return user_prompt, output_dir, problem_statement_language, provider


class StatusDisplay:
    """Context manager for a Claude-like, scrollable, streaming status log."""

    def __init__(self, title="Generating project"):
        self.title = title
        self.messages = []
        self.current_phase = "Preparing pipeline..."
        self.phase_counter = 0
        self._last_completed_phase = None
        self.started_at = time.time()
        self.stats = {"success": 0, "warning": 0, "error": 0, "progress": 0}
        self.max_log_lines = 200
        self.last_error = None
        self.last_traceback = None

    class _LiveLogStream(io.TextIOBase):
        def __init__(self, status_display, stream_name):
            self.status_display = status_display
            self.stream_name = stream_name
            self._buffer = ""

        def write(self, text):
            if not text:
                return 0
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                line = line.rstrip()
                if not line:
                    continue
                if self.stream_name == "stderr":
                    self.status_display.update(line, "error")
                else:
                    self.status_display.update(line, "log")
            return len(text)

        def flush(self):
            if self._buffer.strip():
                line = self._buffer.strip()
                if self.stream_name == "stderr":
                    self.status_display.update(line, "error")
                else:
                    self.status_display.update(line, "log")
            self._buffer = ""

    def stdout_stream(self):
        return self._LiveLogStream(self, "stdout")

    def stderr_stream(self):
        return self._LiveLogStream(self, "stderr")

    def add_exception(self, prefix, exc):
        self.last_error = f"{prefix}: {exc}"
        self.last_traceback = traceback.format_exc()
        self.update(self.last_error, "error")
        if self.last_traceback:
            for line in self.last_traceback.strip().splitlines()[-8:]:
                self.update(line, "error")

    def _elapsed(self):
        elapsed = int(time.time() - self.started_at)
        mins, secs = divmod(elapsed, 60)
        return f"{mins:02d}:{secs:02d}"

    def _time(self):
        return time.strftime("%H:%M:%S")

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

    def _remember_message(self, line):
        self.messages.append(line)
        if len(self.messages) > self.max_log_lines:
            self.messages = self.messages[-self.max_log_lines:]

    def _print_event(self, label, message, style):
        line = Text()
        line.append(f"[{self._time()}] ", style=NEON_MUTED)
        line.append(f"{label} ", style=style)
        line.append(message, style=style)
        console.print(line)
        self._remember_message(f"[{self._time()}] {label} {message}")

    def _print_run_banner(self):
        console.print(self._header())
        console.print(Text("Streaming logs (scrollable)", style=NEON_MUTED))

    def _mark_current_phase_complete(self):
        if self.current_phase and self.current_phase != "Preparing pipeline...":
            if self.current_phase != self._last_completed_phase:
                self._print_event("✓", self.current_phase, NEON_SUCCESS)
                self._last_completed_phase = self.current_phase

    def __enter__(self):
        self._print_run_banner()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._mark_current_phase_complete()
        summary = Text()
        summary.append("Summary  ", style=f"bold {NEON_ACCENT}")
        summary.append(self._elapsed(), style=NEON_INFO)
        summary.append("  •  ", style=NEON_MUTED)
        summary.append(self._stats_line())
        console.print(summary)
        console.print()

    def update(self, message, event_type="progress"):
        """Stream a status line to terminal output (scrollback-friendly)."""
        if event_type == "step":
            self._mark_current_phase_complete()
            self.phase_counter += 1
            self.current_phase = f"{self.phase_counter}. {message}"
            console.print()
            self._print_event("▶", self.current_phase, NEON_PRIMARY)
            self.stats["progress"] += 1
        elif event_type == "success":
            self._print_event("✓", message, NEON_SUCCESS)
            self.stats["success"] += 1
        elif event_type == "error":
            self._print_event("✗", message, NEON_ERROR)
            self.stats["error"] += 1
            self.last_error = message
        elif event_type == "warning":
            self._print_event("⚠", message, NEON_WARNING)
            self.stats["warning"] += 1
        else:
            self._print_event("•", message, "white")
            self.stats["progress"] += 1


def print_success(message):
    console.print(f"[bold {NEON_SUCCESS}]✓ {message}[/bold {NEON_SUCCESS}]")


def print_error(message):
    console.print(f"[bold {NEON_ERROR}]✗ {message}[/bold {NEON_ERROR}]")
