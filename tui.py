#!/usr/bin/env python3
"""
AlphaStack TUI v2 — Interactive Project Orchestrator Dashboard
"""

import os
import sys
import time
import json
import tty
import termios
import threading
from datetime import datetime
from typing import Optional, Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import pyfiglet
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.live import Live
from rich.tree import Tree
from rich import box
from rich.columns import Columns
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    TimeElapsedColumn, MofNCompleteColumn
)

# ── Palette ────────────────────────────────────────────────────────────────────
R  = "#E40066"   # Crimson
G  = "#00FF88"   # Neon Green
B  = "#00AAFF"   # Electric Blue
Y  = "#FFDD00"   # Amber
P  = "#BB44FF"   # Violet
O  = "#FF8800"   # Orange
D  = "dim white"
W  = 88          # Layout width reference

PHASE_ORDER = ["SETUP", "CONFIG", "BLUEPRINT", "FILES", "DEPS", "TESTS"]

PHASE_META = {
    "SETUP":     ("⚡", B,  "System Init"),
    "CONFIG":    ("⚙", Y,  "Configuration"),
    "BLUEPRINT": ("🗺", P,  "Architecture"),
    "FILES":     ("🔨", O,  "File Synthesis"),
    "DEPS":      ("🔗", B,  "Dependency Graph"),
    "TESTS":     ("🧪", G,  "Verification"),
}

SPINNER = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

# ── Provider / Model catalogue ─────────────────────────────────────────────────
PROVIDERS_JSON = os.path.join(PROJECT_ROOT, "src", "providers.json")

def _load_providers() -> Dict:
    try:
        with open(PROVIDERS_JSON) as f:
            return json.load(f)
    except Exception:
        return {"default_provider": "google", "model_providers": {}}

def _save_providers(data: Dict):
    try:
        with open(PROVIDERS_JSON, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

console = Console()


class AlphaStackTUI:
    def __init__(self):
        self.console = Console()
        self.layout  = Layout()

        self.status_phases: Dict[str, str] = {p: "WAITING" for p in PHASE_ORDER}
        self.phase_timings: Dict[str, float] = {}
        self.logs: List[Text] = []
        self.session_history: List[Dict] = []   # keeps summary of past runs
        self.current_phase = "SETUP"
        self.project_details: Dict = {}

        self._live: Optional[Live] = None        # single long-lived Live instance
        self._log_lock = threading.Lock()

        self._setup_layout()

    # ── Layout helpers ─────────────────────────────────────────────────────────

    def _setup_layout(self):
        self.layout.split(
            Layout(name="header",  size=8),
            Layout(name="body"),
            Layout(name="footer",  size=3),
        )
        self.layout["body"].split_row(
            Layout(name="sidebar", ratio=1),
            Layout(name="main",    ratio=3),
        )
        self._refresh_header()
        self._refresh_footer("↑ ↓  Navigate   Enter  Confirm   Q  Quit")
        self._refresh_sidebar()
        self._refresh_main(Panel(
            Align.center(Text("Initialising AutoStack…", style=D)),
            border_style=D,
        ))

    def _refresh_header(self):
        """Render the big ASCII logo + subtitle bar."""
        fig = pyfiglet.Figlet(font="slant", width=W)
        logo = Text(fig.renderText("AUTOSTACK"), style=f"bold {R}")
        sub  = Text(
            "  ◈  ADVANCED  PROJECT  ORCHESTRATOR  ◈  ",
            style=f"bold {D}",
        )
        self.layout["header"].update(Panel(
            Group(Align.center(logo), Align.center(sub)),
            border_style=R,
            box=box.DOUBLE_EDGE,
        ))

    def _refresh_footer(self, message: str, style: str = D):
        self.layout["footer"].update(Panel(
            Align.center(Text(message, style=style)),
            border_style=D,
            box=box.HORIZONTALS,
        ))

    def _refresh_sidebar(self):
        """Phase progress + session history."""
        t = int(time.time() * 6)
        spin = SPINNER[t % len(SPINNER)]

        phase_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        phase_tbl.add_column("ic",   width=2, no_wrap=True)
        phase_tbl.add_column("name", ratio=1)
        phase_tbl.add_column("st",   width=6, no_wrap=True)

        for phase in PHASE_ORDER:
            ph_icon, color, label = PHASE_META[phase]
            status  = self.status_phases[phase]
            elapsed = self.phase_timings.get(phase)

            if status == "RUNNING":
                ic = Text(spin,    style=f"bold {color}")
                nm = Text(label,   style=f"bold {color}")
                st = Text("RUN",   style=f"bold {color}")
            elif status == "DONE":
                ic   = Text("✓",  style=f"bold {G}")
                nm   = Text(label, style=G)
                st_s = f"{elapsed:.1f}s" if elapsed else "OK"
                st   = Text(st_s,  style=f"dim {G}")
            elif status == "FAILED":
                ic = Text("✗",    style=f"bold {R}")
                nm = Text(label,   style=R)
                st = Text("FAIL",  style=f"bold {R}")
            else:
                ic = Text(ph_icon, style=D)
                nm = Text(label,   style=D)
                st = Text("",      style=D)

            phase_tbl.add_row(ic, nm, st)

        # Session history
        hist_lines: List[Text] = []
        if self.session_history:
            hist_lines.append(Text(""))
            hist_lines.append(Text("HISTORY", style=f"bold {D}"))
            for i, s in enumerate(self.session_history[-5:], 1):
                ok  = s.get("success", False)
                clr = G if ok else Y
                name = (s.get("name", "project") or "project")[:14]
                hist_lines.append(
                    Text(f"  #{i} {name}", style=clr)
                )

        self.layout["sidebar"].update(Panel(
            Group(phase_tbl, *hist_lines),
            title=Text("STATUS", style=f"bold {B}"),
            border_style=B,
            box=box.ROUNDED,
            padding=(0, 1),
        ))

    def _refresh_main(self, content):
        self.layout["main"].update(content)

    # ── Logging ────────────────────────────────────────────────────────────────

    def log(self, message: str, style: str = D):
        ts = datetime.now().strftime("%H:%M:%S")
        with self._log_lock:
            self.logs.append(Text(f"[{ts}] {message}", style=style))
            if len(self.logs) > 40:
                self.logs.pop(0)

    def _log_panel(self, n: int = 12) -> Panel:
        with self._log_lock:
            lines = list(self.logs[-n:])
        return Panel(
            Group(*lines) if lines else Text("No logs yet.", style=D),
            title=Text("ACTIVITY LOG", style=f"bold {D}"),
            border_style=D,
            box=box.ROUNDED,
            padding=(0, 1),
        )

    # ── Key reading ────────────────────────────────────────────────────────────

    def _get_key(self) -> str:
        """Read one keypress; handles escape sequences."""
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                try:
                    ch += sys.stdin.read(2)
                except Exception:
                    pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch

    # ── Interactive widgets ────────────────────────────────────────────────────

    def select_menu(
        self,
        options: List[str],
        title: str,
        subtitle: str = "",
        annotations: Optional[Dict[str, str]] = None,
    ) -> str:
        """Keyboard-navigable menu rendered inside the live layout."""
        cur = 0
        annotations = annotations or {}
        self._refresh_footer("↑ ↓  Navigate   Enter  Select   Q  Quit")

        while True:
            rows: List[Text] = []
            if subtitle:
                rows.append(Text(subtitle, style=D))
                rows.append(Text(""))

            for i, opt in enumerate(options):
                ann = annotations.get(opt, "")
                if i == cur:
                    prefix = Text(f" ▶ ", style=f"bold {G}")
                    label  = Text(opt, style=f"bold {G}")
                    suffix = Text(f"  {ann}", style=f"dim {G}") if ann else Text("")
                    row    = Text.assemble(prefix, label, suffix)
                else:
                    prefix = Text(f"   ", style=D)
                    label  = Text(opt, style=D)
                    suffix = Text(f"  {ann}", style=D) if ann else Text("")
                    row    = Text.assemble(prefix, label, suffix)
                rows.append(row)

            self._refresh_main(Panel(
                Align.center(Group(*rows), vertical="middle"),
                title=Text(title, style=f"bold {R}"),
                border_style=R,
                box=box.ROUNDED,
                padding=(1, 3),
            ))
            self._refresh_sidebar()

            k = self._get_key()
            if k in ("\x1b[A", "k"):
                cur = (cur - 1) % len(options)
            elif k in ("\x1b[B", "j"):
                cur = (cur + 1) % len(options)
            elif k in ("\n", "\r"):
                return options[cur]
            elif k in ("q", "Q", "\x03"):
                sys.exit(0)

    def interactive_input(
        self,
        prompt: str,
        default: str = "",
        hint: str = "",
    ) -> str:
        """Inline text input rendered inside the live layout."""
        buf = str(default)
        self._refresh_footer("Type your answer and press Enter")

        while True:
            hint_text = Text(f"  hint: {hint}", style=D) if hint else Text("")
            cursor_line = Text(f" {buf}█", style=f"bold {G}")
            input_box = Panel(cursor_line, border_style=B, padding=(0, 2))

            self._refresh_main(Panel(
                Align.center(Group(
                    Text(""),
                    Text(prompt, style=f"bold {B}"),
                    hint_text,
                    Text(""),
                    input_box,
                    Text(""),
                ), vertical="middle"),
                title=Text("INPUT", style=f"bold {B}"),
                border_style=B,
                box=box.ROUNDED,
                padding=(1, 3),
            ))

            k = self._get_key()
            if k in ("\n", "\r"):
                return buf
            elif k in ("\x7f", "\x08"):
                buf = buf[:-1]
            elif k == "\x03":
                raise KeyboardInterrupt
            elif len(k) == 1 and k.isprintable():
                buf += k

    # ── Phase screens ──────────────────────────────────────────────────────────

    def _provider_config_screen(self) -> Tuple[str, str]:
        """
        Let the user pick a provider, see the currently configured model,
        and optionally change it.  Returns (provider_name, model_name).
        """
        providers_data = _load_providers()
        prov_cfg = providers_data.get("model_providers", {})
        available = list(prov_cfg.keys())
        current_default = providers_data.get("default_provider", "google")

        # annotations: show model alongside provider name
        anns = {p: prov_cfg.get(p, {}).get("model", "?") for p in available}

        provider = self.select_menu(
            available,
            title="SELECT INTELLIGENCE PROVIDER",
            subtitle=f"Current default: {current_default}",
            annotations=anns,
        )

        model_now = prov_cfg.get(provider, {}).get("model", "")

        # Ask to keep or change
        choice = self.select_menu(
            [f"Use current  ({model_now})", "Enter custom model"],
            title=f"MODEL FOR  {provider.upper()}",
            subtitle=f"Provider: {provider}   |   Active model: {model_now}",
        )

        if "custom" in choice:
            model_now = self.interactive_input(
                f"Enter model name for {provider}",
                default=model_now,
                hint="e.g.  google/gemini-2.0-flash  or  gpt-4o",
            )
            # Persist change
            if provider in providers_data["model_providers"]:
                providers_data["model_providers"][provider]["model"] = model_now
            _save_providers(providers_data)
            self.log(f"Model updated → {model_now}", Y)

        return provider, model_now

    def _show_blueprint(self, blueprint):
        sb  = blueprint.software_blueprint_details
        ff  = blueprint.file_formats
        tech = sb.get("tech_stack", "N/A")
        if isinstance(tech, list):
            tech = ", ".join(tech)
        feats = sb.get("features", [])
        if isinstance(feats, list):
            feats = ", ".join(str(f) for f in feats[:4])
            if len(sb.get("features", [])) > 4:
                feats += " …"

        tbl = Table(show_header=False, box=box.SIMPLE_HEAVY, min_width=52, padding=(0, 1))
        tbl.add_column("key",   style=D,          no_wrap=True)
        tbl.add_column("val",   style=f"bold {B}", no_wrap=False)
        tbl.add_row("Project",    sb.get("project_name", "N/A"))
        tbl.add_row("Language",   sb.get("language", "N/A"))
        tbl.add_row("Type",       sb.get("project_type", "N/A"))
        tbl.add_row("Framework",  sb.get("framework", "N/A"))
        tbl.add_row("Tech Stack", tech)
        tbl.add_row("Features",   feats or "N/A")
        tbl.add_row("Files",      str(len(ff)))

        self._refresh_main(Panel(
            Align.center(Group(
                Text(""),
                Text("ARCHITECTURAL BLUEPRINT", style=f"bold {P}"),
                Text(""),
                tbl,
                Text(""),
                Text("Building dependency contracts…", style=D),
            ), vertical="middle"),
            title=Text("BLUEPRINT", style=f"bold {P}"),
            border_style=P,
            box=box.ROUNDED,
        ))

    def _show_file_progress(
        self, orchestrator, oc_thread: threading.Thread, total_files: int
    ):
        """Poll tracker; keep TUI live until the orchestrator thread actually exits.

        Bug fixed: previously broke on `completed >= total_files` which fires
        prematurely during retry rounds (orchestrator calls reset_file() → file
        disappears from failed, then re-appears → completed briefly == total but
        the orchestrator is still running). We now loop on `oc_thread.is_alive()`
        so the display stays live through every retry round.
        """
        progress = Progress(
            SpinnerColumn(spinner_name="dots2", style=f"bold {G}"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, complete_style=G, finished_style=G),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
            expand=True,
        )
        task_id = progress.add_task(
            f"[bold {G}]Synthesising files…", total=total_files
        )

        seen_done:   set = set()
        seen_failed: set = set()
        fail_counts: Dict[str, int] = {}     # how many times each file has failed
        last_progress_t = time.time()
        stall_warned_at: Dict[int, bool] = {}
        STALL_THRESHOLDS = [30, 60, 120, 180, 300]

        self._refresh_footer(
            f"Generating {total_files} files in parallel — retries happen automatically",
            style=D,
        )

        while oc_thread.is_alive():
            done_list   = set(orchestrator.tracker.list_done())
            failed_list = set(orchestrator.tracker.list_failed())

            new_done   = done_list   - seen_done
            new_failed = failed_list - seen_failed
            # Files that were failed last tick but are no longer (reset for retry)
            retrying   = seen_failed - failed_list - done_list

            for fp in sorted(new_done):
                n = fail_counts.get(fp, 0)
                suffix = f" (after {n} retr{'ies' if n > 1 else 'y'})" if n else ""
                self.log(f"✓  {os.path.basename(fp)}{suffix}", G)

            for fp in sorted(new_failed):
                fail_counts[fp] = fail_counts.get(fp, 0) + 1
                n = fail_counts[fp]
                self.log(f"✗  {os.path.basename(fp)} — attempt {n} failed, will retry", R)

            for fp in sorted(retrying):
                n = fail_counts.get(fp, 0)
                self.log(f"↻  {os.path.basename(fp)} — retrying (attempt {n + 1})…", Y)

            if new_done or new_failed:
                last_progress_t = time.time()
                stall_warned_at.clear()

            seen_done   = done_list
            seen_failed = failed_list

            # Show done + currently-failed (excludes files being retried, so can be < total)
            completed = len(done_list) + len(failed_list)
            pending   = total_files - len(done_list) - len(failed_list)

            stall_secs = int(time.time() - last_progress_t)
            for thresh in STALL_THRESHOLDS:
                if stall_secs >= thresh and not stall_warned_at.get(thresh) and pending > 0:
                    stall_warned_at[thresh] = True
                    self.log(
                        f"⏳  {pending} file{'s' if pending > 1 else ''} in progress "
                        f"({stall_secs}s without new completion) — agent still working…",
                        Y,
                    )

            progress.update(task_id, completed=completed)

            split = Layout()
            split.split_column(
                Layout(self._log_panel(10), name="logs",     ratio=2),
                Layout(Panel(progress,
                             title=Text("SYNTHESIS", style=f"bold {O}"),
                             border_style=O, box=box.ROUNDED),
                       name="progress", size=5),
            )
            self._refresh_main(split)
            self._refresh_sidebar()
            time.sleep(0.15)

        # Thread exited — show final counts
        done_list   = set(orchestrator.tracker.list_done())
        failed_list = set(orchestrator.tracker.list_failed())
        progress.update(task_id, completed=len(done_list) + len(failed_list))
        self._refresh_sidebar()

    def _show_test_progress(self, test_thread: threading.Thread):
        """Animated test-running view. Heartbeat every 60s when the log goes silent."""
        progress = Progress(
            SpinnerColumn(spinner_name="bouncingBall", style=f"bold {G}"),
            TextColumn(f"[{G}]Running verification suite…"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        progress.add_task("verify", total=None)   # indeterminate

        self._refresh_footer(
            "Verification running — agent may run tests, patch files, and retry automatically",
            style=D,
        )

        last_log_count = len(self.logs)
        last_activity_t = time.time()
        heartbeat_interval = 45   # seconds of log silence before heartbeat
        heartbeat_n = 0

        while test_thread.is_alive():
            # Heartbeat when log has been silent
            cur_count = len(self.logs)
            if cur_count != last_log_count:
                last_log_count = cur_count
                last_activity_t = time.time()
                heartbeat_n = 0
            elif time.time() - last_activity_t >= heartbeat_interval:
                heartbeat_n += 1
                elapsed = int(time.time() - last_activity_t)
                self.log(
                    f"⏳  Planner still active — {elapsed}s since last event "
                    f"(LLM inference or long test run)",
                    Y,
                )
                last_activity_t = time.time()   # reset so next heartbeat is +45s

            split = Layout()
            split.split_column(
                Layout(Panel(
                    Align.center(Group(
                        Text(""),
                        Text("AUTOMATED TEST & REPAIR LOOP", style=f"bold {G}"),
                        Text(""),
                        progress,
                    )),
                    border_style=G, box=box.ROUNDED,
                    title=Text("VERIFICATION", style=f"bold {G}"),
                ), name="test_hdr", size=7),
                Layout(self._log_panel(14), name="logs"),
            )
            self._refresh_main(split)
            self._refresh_sidebar()
            time.sleep(0.2)

    def show_final_result(
        self,
        blueprint,
        tree,
        timing: float,
        project_path: str,
        success: bool,
        trs: Dict,
        phase_timings: Dict[str, float],
        provider: str,
        model: str,
        total_files: int,
        files_done: int,
        files_failed: int,
        total_tokens: int,
        error_tracker=None,
    ):
        self.current_phase = "SUMMARY"
        sb     = blueprint.software_blueprint_details
        color  = G if success else Y
        status = "ALL TESTS PASSED ✓" if success else ("GAVE UP" if trs.get("gave_up") else "ISSUES REMAIN ⚠")

        # ── Overview table ────────────────────────────────────────────────────
        ov = Table(show_header=False, box=box.SIMPLE_HEAVY, padding=(0, 1))
        ov.add_column("k", style=D, no_wrap=True)
        ov.add_column("v", style=f"bold {color}", no_wrap=False)
        tech = sb.get("tech_stack", "N/A")
        if isinstance(tech, list):
            tech = ", ".join(tech)
        ov.add_row("Project",    sb.get("project_name", "N/A"))
        ov.add_row("Outcome",    status)
        ov.add_row("Language",   sb.get("language", "N/A"))
        ov.add_row("Tech Stack", tech)
        ov.add_row("Provider",   f"{provider} / {model}")
        ov.add_row("Location",   project_path)

        # ── Phase timing table ────────────────────────────────────────────────
        pt = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        pt.add_column("phase",  style=D,  no_wrap=True)
        pt.add_column("bar",    ratio=1)
        pt.add_column("time",   justify="right", no_wrap=True, style=Y)
        max_t = max((phase_timings.get(ph, 0) for ph in PHASE_ORDER), default=1) or 1
        for ph in PHASE_ORDER:
            t = phase_timings.get(ph, 0)
            if not t:
                continue
            clr   = G if self.status_phases[ph] == "DONE" else R
            bar_w = max(1, int((t / max_t) * 18))
            bar   = Text("█" * bar_w, style=clr)
            pt.add_row(
                Text(PHASE_META[ph][2], style=D),
                bar,
                Text(f"{t:.1f}s", style=clr),
            )

        # ── Stats ─────────────────────────────────────────────────────────────
        st = Table(show_header=False, box=None, padding=(0, 1))
        st.add_column("k", style=D,  no_wrap=True)
        st.add_column("v", no_wrap=True)
        st.add_row("Total time",    Text(f"{timing:.1f}s",  style=f"bold {Y}"))
        st.add_row("Files done",    Text(f"{files_done}/{total_files}", style=f"bold {G}"))
        if files_failed:
            st.add_row("Files failed", Text(str(files_failed), style=f"bold {R}"))
        st.add_row("Tool calls",    Text(str(trs.get("tool_calls", "?")), style=f"bold {B}"))
        st.add_row("Tokens used",   Text(f"{total_tokens:,}", style=f"bold {P}"))

        left_panel = Panel(
            Group(
                Text("OVERVIEW", style=f"bold {D}"),
                ov,
                Text(""),
                Text("PHASE TIMINGS", style=f"bold {D}"),
                pt,
                Text(""),
                Text("METRICS", style=f"bold {D}"),
                st,
            ),
            border_style=color, box=box.ROUNDED,
        )

        # ── Folder tree ───────────────────────────────────────────────────────
        tree_view = self._render_tree(tree)

        # ── Fix / Error report (test_runner style) ────────────────────────────
        report_lines: List[Text] = []
        if error_tracker is not None:
            n_errors  = len(error_tracker.error_history)
            n_changes = len(error_tracker.change_log)

            report_lines.append(Text(f"Errors recorded: {n_errors}   Fixes attempted: {n_changes}",
                                     style=f"bold {D}"))
            report_lines.append(Text(""))

            # Change log — last 5 entries
            if error_tracker.change_log:
                report_lines.append(Text("RECENT FIXES", style=f"bold {D}"))
                for c in error_tracker.change_log[-5:]:
                    icon = "✓" if not c.get("error") else "⚙"
                    clr  = G   if not c.get("error") else Y
                    desc = (c.get("change_description") or "")[:70]
                    fp   = os.path.basename(c.get("file", "?"))
                    report_lines.append(Text(f"  {icon} {fp}: {desc}", style=clr))
                report_lines.append(Text(""))

        # Command log summary from .alpha_stack/command_logs.json
        cmd_log_path = os.path.join(project_path, ".alpha_stack", "command_logs.json")
        try:
            if os.path.exists(cmd_log_path):
                with open(cmd_log_path) as f:
                    cmd_data = json.load(f)
                cmds = cmd_data.get("commands", [])
                if cmds:
                    passed_cmds = sum(1 for c in cmds if c.get("success"))
                    report_lines.append(Text(
                        f"COMMANDS RUN: {len(cmds)}  ✓ {passed_cmds}  ✗ {len(cmds)-passed_cmds}",
                        style=f"bold {D}",
                    ))
                    for c in cmds[-4:]:  # last 4 commands
                        ok  = c.get("success", False)
                        cmd = (c.get("command") or "")[:60]
                        report_lines.append(Text(
                            f"  {'✓' if ok else '✗'} {cmd}",
                            style=G if ok else R,
                        ))
        except Exception:
            pass

        right_panel = Panel(
            Group(
                Text("FOLDER STRUCTURE", style=f"bold {B}"),
                Text(""),
                tree_view,
                Text(""),
                Text("REPORT", style=f"bold {D}"),
                *report_lines,
                Text(""),
                Text("NEXT STEP", style=f"bold {D}"),
                Text(f"  cd {project_path}", style=f"bold {G}"),
            ),
            border_style=B, box=box.ROUNDED,
        )

        cols = Columns([left_panel, right_panel], expand=True, equal=True)
        header_msg = Text(f"✦  AUTOSTACK SESSION COMPLETE  ✦", style=f"bold {color}", justify="center")

        self._refresh_main(Panel(
            Group(Text(""), header_msg, Text(""), cols),
            border_style=color,
            box=box.DOUBLE_EDGE,
            title=Text("FINAL REPORT", style=f"bold {color}"),
        ))

    def _render_tree(self, node, rich_tree: Optional[Tree] = None) -> Tree:
        if rich_tree is None:
            rich_tree = Tree(Text.assemble(
                Text("📂 ", style=""),
                Text(node.value, style=f"bold {B}"),
            ))
        if hasattr(node, "children") and node.children:
            for child in sorted(node.children, key=lambda x: x.value):
                if hasattr(child, "children") and child.children:
                    branch = rich_tree.add(Text.assemble(
                        Text("📁 "), Text(child.value, style=f"bold {B}"),
                    ))
                    self._render_tree(child, branch)
                else:
                    rich_tree.add(Text.assemble(
                        Text("📄 "), Text(child.value, style=D),
                    ))
        return rich_tree

    def _session_transition(self, session_summary: Dict):
        """Transition card shown after a session completes."""
        ok      = session_summary.get("success", False)
        name    = session_summary.get("name", "project")
        color   = G if ok else Y
        label   = "PASSED" if ok else "COMPLETED"
        timing  = session_summary.get("timing", 0)
        tokens  = session_summary.get("tokens", 0)
        f_done  = session_summary.get("files_done", 0)

        # Phase timing mini-bars
        pt_rows: List[Text] = []
        max_t = max((self.phase_timings.get(ph, 0) for ph in PHASE_ORDER), default=1) or 1
        for ph in PHASE_ORDER:
            t = self.phase_timings.get(ph, 0)
            if not t:
                continue
            bar_w = max(1, int((t / max_t) * 14))
            clr   = G if self.status_phases.get(ph) == "DONE" else R
            bar   = "█" * bar_w
            pt_rows.append(Text(
                f"  {PHASE_META[ph][2]:<18} {bar:<14} {t:.1f}s",
                style=clr,
            ))

        card = Panel(
            Align.center(Group(
                Text(""),
                Text(f"'{name}'  —  {label}", style=f"bold {color}"),
                Text(""),
                Text(f"  Total: {timing:.1f}s   Files: {f_done}   Tokens: {tokens:,}", style=D),
                Text(""),
                *pt_rows,
                Text(""),
                Text("Enter → new session     Q → quit", style=f"dim {B}"),
                Text(""),
            ), vertical="middle"),
            border_style=color,
            box=box.DOUBLE_EDGE,
            title=Text("SESSION COMPLETE", style=f"bold {color}"),
        )
        self._refresh_main(card)
        self._refresh_footer("Enter → New Session   Q → Quit", style=f"bold {B}")

        while True:
            k = self._get_key()
            if k in ("\n", "\r"):
                return True
            elif k in ("q", "Q", "\x03"):
                return False

    _STATUS_ICONS = {
        "step":     ("›",  D),
        "progress": ("…",  B),
        "success":  ("✓",  G),
        "error":    ("✗",  R),
        "warning":  ("⚠",  Y),
        "tool_call":("⚙",  P),
    }

    def _on_test_status(self, event_type: str, message: str, **_kw):
        """Route testing-pipeline status events into the live log."""
        icon, style = self._STATUS_ICONS.get(event_type, ("·", D))
        # Trim very long messages (tool output etc.)
        short = message if len(message) <= 100 else message[:97] + "…"
        self.log(f"{icon}  {short}", style)

    def _show_error(self, title: str, message: str, detail: str = "", recoverable: bool = True):
        """
        Show an in-TUI error panel without collapsing the window.
        If recoverable=True, prompts the user to retry or quit.
        Returns True if the user wants to retry, False to quit.
        """
        hint = "Enter → Retry   Q → Quit" if recoverable else "Q → Quit   Enter → Quit"
        lines = [
            Text(""),
            Text(f"  {message}", style=f"bold {R}"),
        ]
        if detail:
            # Wrap long detail lines
            for chunk in detail.split("\n")[:8]:
                lines.append(Text(f"  {chunk[:120]}", style=D))
        lines += [
            Text(""),
            Text(f"  {hint}", style=f"dim {Y}"),
            Text(""),
        ]
        self._refresh_main(Panel(
            Align.center(Group(*lines), vertical="middle"),
            title=Text(f"  ✗  {title}  ", style=f"bold {R}"),
            border_style=R,
            box=box.DOUBLE_EDGE,
        ))
        self._refresh_footer(hint, style=f"bold {R}")

        while True:
            k = self._get_key()
            if k in ("\n", "\r"):
                return recoverable   # True = retry, False = quit
            elif k in ("q", "Q", "\x03"):
                return False

    def reset_state(self):
        self.status_phases = {p: "WAITING" for p in PHASE_ORDER}
        self.phase_timings  = {}
        self.logs           = []
        self.current_phase  = "SETUP"
        self._refresh_sidebar()
        self.log("System reset for new session.", D)

    # ── Main entry point ───────────────────────────────────────────────────────

    def start(self):
        from src.utils.prompt_manager import PromptManager
        from src.generator import generate_project_blueprint, generate_tree
        from src.orchestrator import ParallelOrchestrator
        from src.utils.dependencies import DependencyAnalyzer, build_dependency_graph_tree
        from src.utils.error_tracker import ErrorTracker
        from src.testing.testing import run_testing_pipeline
        from src.utils.inference import InferenceManager

        # Single Live context for the entire process
        with Live(
            self.layout,
            refresh_per_second=10,
            screen=True,
            console=self.console,
        ) as self._live:

            while True:  # ── session loop ─────────────────────────────────────
                self.reset_state()
                _quit = False

                # ── SETUP ────────────────────────────────────────────────────
                t_phase = time.time()
                self.status_phases["SETUP"] = "RUNNING"
                self._refresh_sidebar()
                self.log("AutoStack intelligence system active.", B)
                time.sleep(0.4)
                self.status_phases["SETUP"] = "DONE"
                self.phase_timings["SETUP"] = time.time() - t_phase
                self._refresh_sidebar()

                # ── CONFIG: provider + model ──────────────────────────────────
                t_phase = time.time()
                self.status_phases["CONFIG"] = "RUNNING"
                self.current_phase = "CONFIG"
                self._refresh_sidebar()

                provider, model = self._provider_config_screen()
                self.log(f"Provider: {provider}  |  Model: {model}", G)

                InferenceManager.reset()
                InferenceManager.reset_tokens()
                try:
                    InferenceManager.initialize(provider_name=provider)
                except ValueError as api_err:
                    env_var = f"{provider.upper()}_API_KEY"
                    retry = self._show_error(
                        title="API KEY NOT FOUND",
                        message=str(api_err),
                        detail=(
                            f"Set the environment variable:  {env_var}\n"
                            f"  export {env_var}=your_key_here\n\n"
                            f"Then restart AutoStack, or choose a different provider."
                        ),
                        recoverable=True,
                    )
                    if not retry:
                        break
                    continue   # back to top of session loop → re-pick provider

                base_dir = self.interactive_input(
                    "Workspace directory",
                    default=".",
                    hint="Where generated projects will be saved",
                )
                if base_dir.startswith("cd "):
                    base_dir = base_dir[3:].strip()

                project_goal = self.interactive_input(
                    "Project objective",
                    default="A modern Python utility",
                    hint="Describe what you want built in one sentence",
                )

                self.status_phases["CONFIG"] = "DONE"
                self.phase_timings["CONFIG"] = time.time() - t_phase
                self.log(f"Workspace: {base_dir}", D)
                self.log(f"Goal: {project_goal}", D)
                self._refresh_sidebar()

                try:
                    # ── BLUEPRINT ─────────────────────────────────────────────
                    t_phase = time.time()
                    self.status_phases["BLUEPRINT"] = "RUNNING"
                    self.current_phase = "BLUEPRINT"
                    self._refresh_sidebar()
                    self.log("Computing architectural blueprint…", P)

                    t0 = time.time()
                    pm = PromptManager()
                    bp = generate_project_blueprint(project_goal, pm, provider)

                    if not bp:
                        self.status_phases["BLUEPRINT"] = "FAILED"
                        self.phase_timings["BLUEPRINT"] = time.time() - t_phase
                        self._refresh_sidebar()
                        retry = self._show_error(
                            title="BLUEPRINT FAILED",
                            message="The AI model did not return a valid blueprint.",
                            detail="Check your API key and model, then try again.",
                            recoverable=True,
                        )
                        if not retry:
                            _quit = True
                        continue   # retry or start new session

                    self._show_blueprint(bp)
                    self.log("Blueprint established.", G)
                    self.status_phases["BLUEPRINT"] = "DONE"
                    self.phase_timings["BLUEPRINT"] = time.time() - t_phase
                    self._refresh_sidebar()
                    time.sleep(1.2)

                    # ── FILES ─────────────────────────────────────────────────
                    t_phase = time.time()
                    self.status_phases["FILES"] = "RUNNING"
                    self.current_phase = "FILES"
                    self._refresh_sidebar()
                    self.log("Dispatching parallel file-synthesis agents…", O)

                    sb = bp.software_blueprint_details
                    fs = bp.folder_structure
                    ff = bp.file_formats

                    ft        = generate_tree(fs, project_name="")
                    out_root  = os.path.join(base_dir, "generated_projects")
                    proj_path = os.path.join(out_root, ft.value)

                    oc = ParallelOrchestrator(output_base_dir=proj_path, max_workers=10)
                    oc.set_blueprint(sb, fs, ff)
                    for fp, dt in ff.items():
                        oc.add_node(fp, dt.get("purpose", ""))

                    oc_thread = threading.Thread(target=oc.execute, daemon=True)
                    oc_thread.start()

                    self._show_file_progress(oc, oc_thread, len(ff))
                    oc_thread.join()

                    files_done   = len(oc.tracker.list_done())
                    files_failed = len(oc.tracker.list_failed())
                    self.log(
                        f"Synthesis: {files_done} created, {files_failed} failed.", G
                    )
                    self.status_phases["FILES"] = "DONE"
                    self.phase_timings["FILES"] = time.time() - t_phase
                    self._refresh_sidebar()

                    # ── DEPS ──────────────────────────────────────────────────
                    t_phase = time.time()
                    self.status_phases["DEPS"] = "RUNNING"
                    self.current_phase = "DEPS"
                    self._refresh_sidebar()
                    self.log("Resolving dependency graph…", B)

                    da = DependencyAnalyzer()
                    da.analyze_project_files(proj_path, folder_tree=ft, folder_structure=fs)
                    build_dependency_graph_tree(proj_path, da)

                    self.log("Dependency graph cross-linked.", G)
                    self.status_phases["DEPS"] = "DONE"
                    self.phase_timings["DEPS"] = time.time() - t_phase
                    self._refresh_sidebar()

                    # ── TESTS ─────────────────────────────────────────────────
                    t_phase = time.time()
                    self.status_phases["TESTS"] = "RUNNING"
                    self.current_phase = "TESTS"
                    self._refresh_sidebar()
                    self.log("Deploying automated verification pipeline…", G)

                    et      = ErrorTracker(proj_path)
                    trs_box: List[Dict] = []

                    def _run_tests():
                        r = run_testing_pipeline(
                            project_root=proj_path,
                            software_blueprint=sb,
                            folder_structure=fs,
                            file_output_format=ff,
                            pm=pm,
                            error_tracker=et,
                            dependency_analyzer=da,
                            on_status=self._on_test_status,
                            provider_name=provider,
                        )
                        trs_box.append(r)

                    test_thread = threading.Thread(target=_run_tests, daemon=True)
                    test_thread.start()
                    self._show_test_progress(test_thread)
                    test_thread.join()

                    trs     = trs_box[0] if trs_box else {}
                    success = trs.get("success", False)
                    self.status_phases["TESTS"] = "DONE"
                    self.phase_timings["TESTS"] = time.time() - t_phase
                    self._refresh_sidebar()

                    # ── FINAL RESULT ──────────────────────────────────────────
                    tot_time     = time.time() - t0
                    total_tokens = InferenceManager.get_total_tokens()

                    self.show_final_result(
                        blueprint     = bp,
                        tree          = ft,
                        timing        = tot_time,
                        project_path  = proj_path,
                        success       = success,
                        trs           = trs,
                        phase_timings = self.phase_timings,
                        provider      = provider,
                        model         = model,
                        total_files   = len(ff),
                        files_done    = files_done,
                        files_failed  = files_failed,
                        total_tokens  = total_tokens,
                        error_tracker = et,
                    )

                    self.session_history.append({
                        "name":       sb.get("project_name", "project"),
                        "success":    success,
                        "timing":     tot_time,
                        "files_done": files_done,
                        "tokens":     total_tokens,
                    })

                except Exception as phase_err:
                    import traceback
                    detail = traceback.format_exc()
                    self.log(f"Error: {phase_err}", R)
                    retry = self._show_error(
                        title="SESSION ERROR",
                        message=str(phase_err) or type(phase_err).__name__,
                        detail=detail,
                        recoverable=True,
                    )
                    if not retry:
                        _quit = True

                if _quit:
                    break

                # ── SESSION TRANSITION ────────────────────────────────────────
                if self.session_history:
                    session_ok = self._session_transition(self.session_history[-1])
                    if not session_ok:
                        break

        console.print(f"\n[bold {G}]AutoStack — session ended. Goodbye.[/]\n")


if __name__ == "__main__":
    tui = AlphaStackTUI()
    try:
        tui.start()
    except KeyboardInterrupt:
        console.print(f"\n[bold {Y}]Interrupted.[/]")
    except Exception as exc:
        console.print(f"\n[bold {R}]Fatal error: {exc}[/]")
        import traceback
        traceback.print_exc()
