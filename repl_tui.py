"""
repl_tui.py - Landing screen and terminal UI helpers for the sagent REPL.
"""

from __future__ import annotations

import re
import shutil
import textwrap
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime

from wcwidth import wcswidth

from harness import __version__
from harness.harness import DEFAULT_MODEL

# ANSI colors (kept here so repl.py can import styles without circular deps)
RESET = "\033[0m"
FG_WHITE = "\033[97m"
FG_GREEN = "\033[92m"
FG_CYAN = "\033[96m"
FG_YELLOW = "\033[93m"
FG_MAGENTA = "\033[95m"
FG_DIM = "\033[90m"
FG_RED = "\033[91m"
FG_BLUE = "\033[94m"
FG_BOLD = "\033[1m"

SAGENT_LOGO = r"""
 ███████╗ █████╗ ██████╗ ███████╗███╗   ██╗████████╗
 ██╔════╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
 ███████╗███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
 ╚════██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
 ███████║██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
 ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
""".strip("\n")

MEMORY_ART = r"""
     +--+
    / ## \
   | ### |
    \___/
 HydraDB
""".strip("\n")

ART_COLUMN_WIDTH = 12
LABEL_COLUMN_WIDTH = 12
CMD_COLUMN_WIDTH = 11
COLUMN_GAP = 2

MEMORY_TYPES = [
    ("📝 FACT", "Facts and knowledge"),
    ("⚙️  PREF", "User preferences"),
    ("💬 INTER", "Conversations"),
    ("💡 THOUGHT", "Ideas and notes"),
    ("📅 EVENT", "Events and milestones"),
]

COMMAND_PREVIEW = [
    ("/remember", "Store a fact"),
    ("/save", "Save last exchange"),
    ("/memories", "List recent memories"),
    ("/autosave", "Toggle auto-save"),
    ("/help", "All commands"),
    ("/exit", "Leave the REPL"),
]


def terminal_width(fallback: int = 100) -> int:
    try:
        columns = shutil.get_terminal_size(fallback=(fallback, 24)).columns
    except OSError:
        return fallback
    return max(72, min(columns, 120))


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _display_width(text: str) -> int:
    plain = _strip_ansi(text)
    width = wcswidth(plain)
    return max(width, 0) if width >= 0 else len(plain)


def _visible_len(text: str) -> int:
    return _display_width(text)


def _truncate_display(text: str, max_width: int) -> str:
    if _display_width(text) <= max_width:
        return text
    out: list[str] = []
    used = 0
    for ch in text:
        ch_w = wcswidth(ch)
        if ch_w < 0:
            ch_w = 1
        if used + ch_w > max_width - 1:
            out.append("…")
            break
        out.append(ch)
        used += ch_w
    return "".join(out)


def _pad_display(text: str, width: int, *, align: str = "left") -> str:
    visible = _display_width(text)
    if visible > width:
        return _truncate_display(text, width)
    pad = width - visible
    if align == "center":
        left = pad // 2
        return (" " * left) + text + (" " * (pad - left))
    if align == "right":
        return (" " * pad) + text
    return text + (" " * pad)


def _pad_line(content: str, width: int) -> str:
    return _pad_display(content, width)


def _box_border(width: int, left: str, fill: str, right: str, title: str = "") -> str:
    if title:
        inner = width - 2
        title_block = f" {title} "
        dash_count = max(inner - len(title_block), 0)
        left_dashes = dash_count // 2
        right_dashes = dash_count - left_dashes
        line = left + ("─" * left_dashes) + title_block + ("─" * right_dashes) + right
        return line[: width]
    return left + (fill * (width - 2)) + right


def _box_row(content: str, inner_width: int) -> str:
    return f"{FG_BLUE}│{RESET} {_pad_display(content, inner_width)} {FG_BLUE}│{RESET}"


def _landing_column_widths(inner_width: int) -> tuple[int, int, int, int]:
    """Return art, left-col, right-col, and desc widths for the welcome panel."""
    art_w = ART_COLUMN_WIDTH
    usable = inner_width - art_w - COLUMN_GAP
    col_w = (usable - COLUMN_GAP) // 2
    desc_w = max(col_w - LABEL_COLUMN_WIDTH - 1, 8)
    cmd_desc_w = max(col_w - CMD_COLUMN_WIDTH - 1, 8)
    return art_w, col_w, desc_w, cmd_desc_w


def _format_data_row(
    left_label: str,
    left_desc: str,
    right_label: str,
    right_desc: str,
    *,
    col_w: int,
    desc_w: int,
    cmd_desc_w: int,
    left_label_color: str = FG_CYAN,
    right_label_color: str = FG_GREEN,
) -> str:
    left = (
        f"{left_label_color}{_pad_display(left_label, LABEL_COLUMN_WIDTH)}{RESET}"
        f" {FG_DIM}{_pad_display(left_desc, desc_w)}{RESET}"
    )
    right = (
        f"{right_label_color}{_pad_display(right_label, CMD_COLUMN_WIDTH)}{RESET}"
        f" {FG_DIM}{_pad_display(right_desc, cmd_desc_w)}{RESET}"
    )
    return f"{_pad_display(left, col_w)}  {_pad_display(right, col_w)}"


def _build_panel_rows(
    inner_width: int,
    art_lines: list[str],
) -> list[str]:
    art_w, col_w, desc_w, cmd_desc_w = _landing_column_widths(inner_width)
    rows: list[str] = []

    header = (
        f"{FG_BOLD}{_pad_display('Memory Types', col_w)}{RESET}"
        f"  {FG_BOLD}{_pad_display('Slash Commands', col_w)}{RESET}"
    )
    rows.append(f"{' ' * art_w}{' ' * COLUMN_GAP}{header}")

    separator = (
        f"{FG_DIM}{'─' * col_w}{RESET}  {FG_DIM}{'─' * col_w}{RESET}"
    )
    rows.append(f"{' ' * art_w}{' ' * COLUMN_GAP}{separator}")

    data_rows = max(len(MEMORY_TYPES), len(COMMAND_PREVIEW))
    for i in range(data_rows):
        left = MEMORY_TYPES[i] if i < len(MEMORY_TYPES) else None
        right = COMMAND_PREVIEW[i] if i < len(COMMAND_PREVIEW) else None
        if left and right:
            content = _format_data_row(
                left[0],
                left[1],
                right[0],
                right[1],
                col_w=col_w,
                desc_w=desc_w,
                cmd_desc_w=cmd_desc_w,
            )
        elif right:
            right_part = (
                f"{FG_GREEN}{_pad_display(right[0], CMD_COLUMN_WIDTH)}{RESET}"
                f" {FG_DIM}{_pad_display(right[1], cmd_desc_w)}{RESET}"
            )
            content = f"{' ' * col_w}  {_pad_display(right_part, col_w)}"
        else:
            content = " " * (col_w * 2 + 2)

        if i < len(art_lines):
            art = f"{FG_MAGENTA}{_pad_display(art_lines[i], art_w, align='center')}{RESET}"
            rows.append(f"{art}{' ' * COLUMN_GAP}{content}")
        else:
            rows.append(f"{' ' * art_w}{' ' * COLUMN_GAP}{content}")

    return rows


def memory_count(harness, user_id: str, *, timeout: float = 2.0) -> int | None:
    """Return recent memory count, or None if HydraDB is slow/unavailable."""

    def _fetch() -> int:
        return len(harness.get_recent_memories(user_id, limit=100))

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_fetch).result(timeout=timeout)
    except (FuturesTimeoutError, Exception):
        return None


def build_landing_lines(
    *,
    harness,
    user_id: str,
    model: str = DEFAULT_MODEL,
    session_id: str | None = None,
    version: str = __version__,
    width: int | None = None,
) -> list[str]:
    width = width or terminal_width()
    mem_count = memory_count(harness, user_id)
    mem_label = str(mem_count) if mem_count is not None else "—"
    session_label = session_id[:8] + "…" if session_id else "—"
    today = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = []
    logo_lines = SAGENT_LOGO.splitlines()
    logo_block_w = max(len(line) for line in logo_lines)
    for logo_line in logo_lines:
        centered = logo_line.center(logo_block_w)
        pad = max((width - logo_block_w) // 2, 0)
        lines.append(" " * pad + f"{FG_CYAN}{centered}{RESET}")

    subtitle = f"sagent v{version} · HydraDB memory harness · {today}"
    pad = max((width - len(subtitle)) // 2, 0)
    lines.append(" " * pad + f"{FG_DIM}{subtitle}{RESET}")
    lines.append("")

    lines.append(f"{FG_BLUE}{_box_border(width, '╭', '─', '╮', 'Welcome')}{RESET}")

    inner_width = width - 4
    art_lines = MEMORY_ART.splitlines()
    panel_rows = _build_panel_rows(inner_width, art_lines)

    for row in panel_rows:
        lines.append(_box_row(row, inner_width))

    meta = (
        f"{FG_BOLD}Model{RESET}  {FG_WHITE}{model}{RESET}   "
        f"{FG_BOLD}User{RESET}  {FG_WHITE}{user_id}{RESET}   "
        f"{FG_BOLD}Memories{RESET}  {FG_WHITE}{mem_label}{RESET}   "
        f"{FG_BOLD}Session{RESET}  {FG_WHITE}{session_label}{RESET}"
    )
    lines.append(_box_row(meta, inner_width))

    footer_plain = (
        "12 commands · chat not stored by default · type / for menu · Ctrl+C cancels thinking · "
        "chat freely for agent replies"
    )
    wrapped = textwrap.wrap(footer_plain, width=inner_width) or [footer_plain]
    for row in wrapped:
        styled = f"{FG_DIM}{row}{RESET}".replace(
            "Ctrl+C", f"{FG_GREEN}Ctrl+C{FG_DIM}"
        ).replace(" / ", f" {FG_GREEN}/{FG_DIM} ")
        lines.append(_box_row(styled, inner_width))

    lines.append(f"{FG_BLUE}{_box_border(width, '╰', '─', '╯')}{RESET}")
    lines.append("")
    lines.append(
        f"{FG_GREEN}Welcome to sagent!{RESET} "
        f"{FG_DIM}Persistent memory across sessions — type a message or {FG_GREEN}/help{FG_DIM}.{RESET}"
    )
    lines.append(
        f"{FG_YELLOW}✦ Tip:{RESET} {FG_DIM}Chat is ephemeral — use {FG_GREEN}/save{FG_DIM} or "
        f"{FG_GREEN}/remember{FG_DIM} to persist what matters.{RESET}"
    )
    return lines


def print_landing_screen(
    *,
    harness,
    user_id: str,
    model: str = DEFAULT_MODEL,
    session_id: str | None = None,
    clear: bool = True,
) -> None:
    if clear:
        print("\033[2J\033[H", end="")
    width = terminal_width()
    for line in build_landing_lines(
        harness=harness,
        user_id=user_id,
        model=model,
        session_id=session_id,
        width=width,
    ):
        print(line)
    print("")


def print_status_bar(*, model: str, user_id: str, memory_count: int | None = None) -> None:
    width = terminal_width()
    mem = str(memory_count) if memory_count is not None else "—"
    status = (
        f"{FG_DIM} {FG_CYAN}◆{RESET} {FG_WHITE}{model}{RESET} "
        f"{FG_DIM}│{RESET} user {FG_WHITE}{user_id}{RESET} "
        f"{FG_DIM}│{RESET} memories {FG_WHITE}{mem}{RESET} "
        f"{FG_DIM}│{RESET} backend {FG_WHITE}HydraDB{RESET}"
    )
    status_w = _display_width(status)
    if status_w >= width:
        print(status)
        return
    left = max((width - status_w) // 2, 0)
    right = width - status_w - left
    print(f"{FG_DIM}{'─' * left}{RESET}{status}{FG_DIM}{'─' * right}{RESET}")


def print_prompt_divider() -> None:
    width = terminal_width()
    print(f"{FG_DIM}{'─' * width}{RESET}")


def print_user_message(text: str) -> None:
    print(f"\n{FG_DIM}You:{RESET} {FG_WHITE}{text}{RESET}")


def print_agent_message(text: str) -> None:
    print(f"\n{FG_MAGENTA}{FG_BOLD}Agent{RESET}")
    for line in text.splitlines():
        print(f"{FG_WHITE}  {line}{RESET}")
    print()


def print_success(text: str) -> None:
    print(f"{FG_GREEN}✓ {text}{RESET}")


def print_error(text: str) -> None:
    print(f"{FG_RED}✗ {text}{RESET}")


def print_header(text: str) -> None:
    width = terminal_width()
    bar = f" {text} "
    pad = max((width - len(bar)) // 2, 0)
    print(f"\n{FG_BLUE}{'─' * pad}{bar}{'─' * (width - pad - len(bar))}{RESET}")


def print_system_message(text: str) -> None:
    print(f"{FG_DIM}{text}{RESET}")
