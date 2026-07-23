"""Unit tests for .ai-reviewer.yml parsing and ignore-path matching."""

from app.config_schema import ReviewerConfig
from app.review.schema import Severity


def test_defaults_when_empty():
    cfg = ReviewerConfig.load(None)
    assert cfg.block_severity == Severity.high
    assert cfg.min_confidence == 0.6
    assert cfg.max_files == 50
    assert cfg.passes["correctness"] is True


def test_load_overrides():
    cfg = ReviewerConfig.load(
        """
        passes:
          style: false
          tests: false
        block_severity: medium
        min_confidence: 0.8
        max_files: 10
        llm:
          provider: anthropic
          model: claude-opus-4-8
        """
    )
    assert cfg.passes["style"] is False
    assert cfg.block_severity == Severity.medium
    assert cfg.min_confidence == 0.8
    assert cfg.max_files == 10
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.model == "claude-opus-4-8"


def test_invalid_yaml_falls_back_to_defaults():
    cfg = ReviewerConfig.load("passes: [unclosed")
    assert cfg.block_severity == Severity.high


def test_invalid_schema_falls_back_to_defaults():
    cfg = ReviewerConfig.load("block_severity: not-a-severity")
    assert cfg.block_severity == Severity.high


def test_non_mapping_falls_back():
    assert ReviewerConfig.load("- just\n- a\n- list").max_files == 50


def test_ignore_paths_matching():
    cfg = ReviewerConfig()
    assert cfg.is_ignored("poetry.lock") is True          # **/*.lock, basename
    assert cfg.is_ignored("sub/dir/yarn.lock") is True     # **/*.lock, nested
    assert cfg.is_ignored("dist/app.js") is True           # dist/**
    assert cfg.is_ignored("dist/nested/app.js") is True    # dist/** recursive
    assert cfg.is_ignored("node_modules/pkg/index.js") is True
    assert cfg.is_ignored("src/app.min.js") is True        # *.min.js basename
    assert cfg.is_ignored("src/app.py") is False
    assert cfg.is_ignored("README.md") is False


def test_custom_ignore_paths():
    cfg = ReviewerConfig.load("ignore_paths:\n  - 'docs/**'\n  - '*.md'")
    assert cfg.is_ignored("docs/guide/intro.md") is True
    assert cfg.is_ignored("CHANGELOG.md") is True
    assert cfg.is_ignored("src/app.py") is False
