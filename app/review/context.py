"""Build the textual context handed to the LLM for each review.

Renders the changed files as an annotated diff (new-file line numbers on
added/context lines, removed lines marked) and, when the full file content is
available, a surrounding-code window so the model can reason about correctness
beyond the raw diff lines.
"""

from __future__ import annotations

from collections.abc import Callable

from app.github.diff import DiffFile, ParsedDiff

# A callable that returns the full text of a file at the PR head, or None.
FetchContent = Callable[[str], str | None]


def gather_context(diff: ParsedDiff, fetch: FetchContent | None) -> dict[str, str | None]:
    """Fetch full new-file contents for each changed (non-removed) file."""
    contents: dict[str, str | None] = {}
    for f in diff.files:
        if f.status == "removed" or fetch is None:
            contents[f.filename] = None
        else:
            try:
                contents[f.filename] = fetch(f.filename)
            except Exception:
                contents[f.filename] = None
    return contents


def _render_patch(dfile: DiffFile) -> str:
    lines: list[str] = []
    for ln in dfile.lines:
        if ln.kind == "added":
            lines.append(f"{ln.new_lineno:>6}+ {ln.content}")
        elif ln.kind == "context":
            lines.append(f"{ln.new_lineno:>6}  {ln.content}")
        elif ln.kind == "removed":
            lines.append(f"{'':>6}- {ln.content}")
        elif ln.kind == "hunk":
            lines.append("       @@")
    return "\n".join(lines)


def _render_windows(content: str, changed: list[int], context_lines: int) -> str:
    """Show the new-file lines around each changed line, with `>` markers."""
    file_lines = content.split("\n")
    total = len(file_lines)
    wanted: set[int] = set()
    for ln in changed:
        for n in range(ln - context_lines, ln + context_lines + 1):
            if 1 <= n <= total:
                wanted.add(n)

    out: list[str] = []
    prev = 0
    for n in sorted(wanted):
        if prev and n != prev + 1:
            out.append("       ...")
        marker = ">" if n in changed else " "
        out.append(f"{n:>6}{marker} {file_lines[n - 1]}")
        prev = n
    return "\n".join(out)


def render_for_prompt(
    diff: ParsedDiff,
    contents: dict[str, str | None],
    *,
    context_lines: int = 6,
    max_chars_per_file: int = 6000,
) -> str:
    """Render the whole diff into an LLM-friendly, line-numbered block."""
    parts: list[str] = []
    for f in diff.files:
        header = f"### FILE: {f.filename} (status: {f.status})"
        if f.previous_filename:
            header += f" (renamed from {f.previous_filename})"
        parts.append(header)

        parts.append("--- changed hunks (line numbers are new-file / RIGHT side) ---")
        parts.append(_render_patch(f)[:max_chars_per_file] or "(no textual diff)")

        content = contents.get(f.filename)
        changed = [ln.new_lineno for ln in f.lines if ln.kind == "added" and ln.new_lineno]
        if content and changed:
            window = _render_windows(content, changed, context_lines)
            if window:
                parts.append("--- surrounding code (for context) ---")
                parts.append(window[:max_chars_per_file])

    return "\n\n".join(parts)
