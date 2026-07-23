"""Unit tests for unified-diff parsing and GitHub position mapping."""

from app.github.diff import parse_files, parse_patch

SINGLE = """@@ -1,3 +1,4 @@
 line1
-line2
+line2new
+line3added
 line4"""

MULTI = """@@ -1,2 +1,2 @@
 a
-b
+B
@@ -10,2 +10,2 @@
 c
-d
+D"""

ADDED = """@@ -0,0 +1,3 @@
+alpha
+beta
+gamma"""

REMOVED = """@@ -1,2 +0,0 @@
-x
-y"""

NO_NEWLINE = """@@ -1 +1 @@
-old
\\ No newline at end of file
+new
\\ No newline at end of file"""


def test_single_hunk_positions_and_linenos():
    f = parse_patch("app.py", SINGLE)
    # RIGHT-side (new file) line -> position
    assert f.new_pos == {1: 1, 2: 3, 3: 4, 4: 5}
    # LEFT-side (old file) line -> position
    assert f.old_pos == {1: 1, 2: 2, 3: 5}
    assert f.position_for(3, "RIGHT") == 4
    assert f.position_for(2, "LEFT") == 2
    assert f.commentable_lines("RIGHT") == {1, 2, 3, 4}


def test_added_line_is_commentable_context_on_both_sides():
    f = parse_patch("app.py", SINGLE)
    assert f.is_commentable(3, "RIGHT") is True  # added line
    assert f.is_commentable(1, "RIGHT") is True  # context line
    assert f.is_commentable(99, "RIGHT") is False


def test_multi_hunk_position_continues_across_hunk_header():
    f = parse_patch("mod.py", MULTI)
    # Position keeps increasing through the second @@ header.
    assert f.position_for(10, "RIGHT") == 5
    assert f.position_for(11, "RIGHT") == 7
    assert f.new_pos == {1: 1, 2: 3, 10: 5, 11: 7}


def test_added_file():
    f = parse_patch("new.py", ADDED, status="added")
    assert f.status == "added"
    assert f.new_pos == {1: 1, 2: 2, 3: 3}
    assert f.old_pos == {}
    assert f.commentable_lines("LEFT") == set()


def test_removed_file():
    f = parse_patch("gone.py", REMOVED, status="removed")
    assert f.new_pos == {}
    assert f.old_pos == {1: 1, 2: 2}


def test_renamed_file_keeps_previous_name():
    f = parse_patch(
        "new_name.py", SINGLE, status="renamed", previous_filename="old_name.py"
    )
    assert f.status == "renamed"
    assert f.previous_filename == "old_name.py"


def test_no_newline_marker_occupies_position_but_not_a_line():
    f = parse_patch("x.txt", NO_NEWLINE)
    # The "\ No newline" markers advance position but map no line number.
    assert f.new_pos == {1: 3}
    assert f.old_pos == {1: 1}
    kinds = [ln.kind for ln in f.lines]
    assert kinds == ["removed", "nonewline", "added", "nonewline"]


def test_empty_patch_is_safe():
    f = parse_patch("binary.png", None)
    assert f.lines == []
    assert f.new_pos == {} and f.old_pos == {}


def test_parse_files_builds_lookup_by_name():
    diff = parse_files(
        [
            {"filename": "a.py", "status": "modified", "patch": SINGLE},
            {"filename": "b.py", "status": "added", "patch": ADDED},
            {
                "filename": "c.py",
                "status": "renamed",
                "previous_filename": "old_c.py",
                "patch": MULTI,
            },
        ]
    )
    assert len(diff) == 3
    assert diff.get("b.py").status == "added"
    assert diff.get("c.py").previous_filename == "old_c.py"
    assert diff.get("missing.py") is None
    assert {f.filename for f in diff} == {"a.py", "b.py", "c.py"}
