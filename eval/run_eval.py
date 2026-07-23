"""Run the benchmark and emit a markdown + JSON eval report.

By default it scores the offline heuristic reviewer (no API keys needed):

    python -m eval.run_eval

To score a real model, pass a provider and set the matching API key:

    python -m eval.run_eval --provider openai --model gpt-4o
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.config import get_settings
from app.github.diff import parse_files
from app.review.context import render_for_prompt
from app.review.engine import ReviewEngine
from app.review.llm import LLMClient, build_llm_client
from app.review.passes import build_passes
from eval.heuristics import HeuristicClient
from eval.metrics import CaseScore, aggregate, score_case

BENCHMARK_DIR = Path(__file__).parent / "benchmark"
REPORTS_DIR = Path(__file__).parent / "reports"


def load_cases(benchmark_dir: Path) -> list[dict]:
    cases = []
    for path in sorted(benchmark_dir.glob("*.yml")):
        with open(path, encoding="utf-8") as fh:
            cases.append(yaml.safe_load(fh))
    return cases


def _build_client(provider: str, model: str) -> LLMClient:
    if provider == "heuristic":
        return HeuristicClient()
    settings = get_settings()
    return build_llm_client(
        provider,
        model,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
    )


async def run_case(engine: ReviewEngine, case: dict) -> tuple[CaseScore, list]:
    diff = parse_files(case["files"])
    rendered = render_for_prompt(diff, {})
    started = time.monotonic()
    result = await engine.review(diff, rendered, min_confidence=0.5)
    latency_ms = (time.monotonic() - started) * 1000
    score = score_case(
        case["name"], result.findings, case.get("ground_truth", []) or [], latency_ms
    )
    return score, result.findings


def render_report(summary: dict, scores: list[CaseScore], cases: list[dict], provider: str) -> str:
    lines = [
        "# AI PR Reviewer — Evaluation Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Reviewer: `{provider}`",
        f"- Cases: {summary['num_cases']}",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Precision | {summary['precision']:.2%} |",
        f"| Recall | {summary['recall']:.2%} |",
        f"| F1 | {summary['f1']:.2%} |",
        f"| True positives | {summary['tp']} |",
        f"| False positives | {summary['fp']} |",
        f"| False negatives | {summary['fn']} |",
        f"| Avg latency | {summary['avg_latency_ms']:.1f} ms |",
        "",
        "## By pass",
        "",
        "| Pass | Precision | Recall | TP | FP | FN |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, b in sorted(summary["per_pass"].items()):
        lines.append(
            f"| {name} | {b['precision']:.0%} | {b['recall']:.0%} | "
            f"{b['tp']} | {b['fp']} | {b['fn']} |"
        )

    lines += [
        "",
        "## By case",
        "",
        "| Case | Expected | TP | FP | FN | Latency |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    gt_by_name = {c["name"]: len(c.get("ground_truth", []) or []) for c in cases}
    for s in scores:
        lines.append(
            f"| {s.name} | {gt_by_name.get(s.name, 0)} | {s.tp} | {s.fp} | "
            f"{s.fn} | {s.latency_ms:.1f} ms |"
        )

    example = next((c for c in cases if c.get("ground_truth")), None)
    if example:
        patch = example["files"][0]["patch"].rstrip()
        lines += [
            "",
            "## Example case",
            "",
            f"**{example['name']}** — {example.get('description', '')}",
            "",
            "```diff",
            patch,
            "```",
        ]
    return "\n".join(lines) + "\n"


def _log_eval_run(summary: dict) -> None:
    try:
        from app.db.models import EvalRun
        from app.db.session import SessionLocal, init_db

        init_db()
        db = SessionLocal()
        try:
            db.add(
                EvalRun(
                    num_cases=summary["num_cases"],
                    recall=summary["recall"],
                    precision=summary["precision"],
                    avg_latency_ms=summary["avg_latency_ms"],
                    report=summary,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        print(f"(skipped DB logging: {exc})")


async def main_async(args: argparse.Namespace) -> None:
    cases = load_cases(Path(args.benchmark))
    if not cases:
        raise SystemExit(f"No benchmark cases found in {args.benchmark}")

    client = _build_client(args.provider, args.model)
    engine = ReviewEngine(client, build_passes({}))

    scores: list[CaseScore] = []
    for case in cases:
        score, _ = await run_case(engine, case)
        scores.append(score)

    summary = aggregate(scores)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_md = render_report(summary, scores, cases, args.provider)
    (REPORTS_DIR / "report.md").write_text(report_md, encoding="utf-8")
    (REPORTS_DIR / "report.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    if not args.no_db:
        _log_eval_run(summary)

    print(report_md)
    print(f"Wrote {REPORTS_DIR / 'report.md'} and report.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reviewer benchmark.")
    parser.add_argument("--provider", default="heuristic", help="heuristic | openai | anthropic")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--benchmark", default=str(BENCHMARK_DIR))
    parser.add_argument("--no-db", action="store_true", help="Skip logging to the database.")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
