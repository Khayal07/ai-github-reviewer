"""Unified-diff parsing and GitHub position mapping.

GitHub's PR "files" API returns, per file, a `patch` string containing the
unified-diff hunks for that file (without the `diff --git` / `+++` headers).
To post inline review comments we need, for each commentable line:

* its line number in the new file (RIGHT side) or old file (LEFT side), and
* its *diff position* — the 1-based offset from the first `@@` hunk header,
  counting every subsequent line (including later hunk headers), per the
  GitHub REST API definition.

This module parses those patches without external dependencies so the mapping
is fully under test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class DiffLine:
    position: int
    old_lineno: int | None
    new_lineno: int | None
    kind: str  # context | added | removed | hunk | nonewline
    content: str


@dataclass
class DiffFile:
    filename: str
    status: str = "modified"  # added | modified | removed | renamed | changed
    previous_filename: str | None = None
    patch: str | None = None
    lines: list[DiffLine] = field(default_factory=list)
    new_pos: dict[int, int] = field(default_factory=dict)  # new lineno -> position
    old_pos: dict[int, int] = field(default_factory=dict)  # old lineno -> position

    def _pos_map(self, side: str) -> dict[int, int]:
        return self.new_pos if side.upper() == "RIGHT" else self.old_pos

    def position_for(self, line: int, side: str = "RIGHT") -> int | None:
        """GitHub diff position for a file line, or None if not in the diff."""
        return self._pos_map(side).get(line)

    def is_commentable(self, line: int, side: str = "RIGHT") -> bool:
        return line in self._pos_map(side)

    def commentable_lines(self, side: str = "RIGHT") -> set[int]:
        return set(self._pos_map(side).keys())


@dataclass
class ParsedDiff:
    files: list[DiffFile] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.by_name: dict[str, DiffFile] = {f.filename: f for f in self.files}

    def get(self, filename: str) -> DiffFile | None:
        return self.by_name.get(filename)

    def __iter__(self):
        return iter(self.files)

    def __len__(self) -> int:
        return len(self.files)


def parse_patch(
    filename: str,
    patch: str | None,
    *,
    status: str = "modified",
    previous_filename: str | None = None,
) -> DiffFile:
    """Parse a single file's unified-diff patch into a `DiffFile`."""
    dfile = DiffFile(
        filename=filename,
        status=status,
        previous_filename=previous_filename,
        patch=patch,
    )
    if not patch:
        return dfile

    position = 0
    old_ln = 0
    new_ln = 0
    seen_first_hunk = False

    for raw in patch.split("\n"):
        if raw == "":
            # Trailing artifact of split(); genuine blank context lines are " ".
            continue

        if raw.startswith("@@"):
            match = _HUNK_RE.match(raw)
            if not match:
                continue
            old_ln = int(match.group(1))
            new_ln = int(match.group(2))
            if not seen_first_hunk:
                seen_first_hunk = True
                # First hunk header is position 0; the line below becomes 1.
            else:
                position += 1
                dfile.lines.append(DiffLine(position, None, None, "hunk", raw))
            continue

        if not seen_first_hunk:
            continue

        position += 1
        marker, body = raw[0], raw[1:]

        if marker == "+":
            dfile.lines.append(DiffLine(position, None, new_ln, "added", body))
            dfile.new_pos[new_ln] = position
            new_ln += 1
        elif marker == "-":
            dfile.lines.append(DiffLine(position, old_ln, None, "removed", body))
            dfile.old_pos[old_ln] = position
            old_ln += 1
        elif marker == "\\":
            # "\ No newline at end of file" — occupies a position, no line no.
            dfile.lines.append(DiffLine(position, None, None, "nonewline", raw))
        else:
            # Context line (leading space) — belongs to both sides.
            dfile.lines.append(DiffLine(position, old_ln, new_ln, "context", body))
            dfile.old_pos[old_ln] = position
            dfile.new_pos[new_ln] = position
            old_ln += 1
            new_ln += 1

    return dfile


def parse_files(files_json: list[dict]) -> ParsedDiff:
    """Parse the GitHub PR "files" API payload into a `ParsedDiff`."""
    parsed = [
        parse_patch(
            f["filename"],
            f.get("patch"),
            status=f.get("status", "modified"),
            previous_filename=f.get("previous_filename"),
        )
        for f in files_json
    ]
    return ParsedDiff(files=parsed)
