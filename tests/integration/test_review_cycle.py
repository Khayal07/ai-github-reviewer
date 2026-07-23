"""Integration test: a full review cycle against a mocked GitHub PR."""

import httpx
import respx

from app.config import Settings
from app.github.client import GitHubClient
from app.review.llm import LLMClient
from app.review.schema import Finding, PassType, Severity, Verdict
from app.reviewer import ReviewRequest, run_review

API = "https://api.github.com"

PATCH = """@@ -1,3 +1,4 @@
 def f():
-    return 1
+    x = 1
+    return x
 # end"""

FILE_CONTENT = "def f():\n    x = 1\n    return x\n# end\n"


class _StubLLM(LLMClient):
    """Returns a single high-severity correctness finding; nothing else."""

    async def review(self, *, system, user, pass_type):
        if pass_type == PassType.correctness:
            return [
                Finding(
                    file="app.py", line=3, severity=Severity.high,
                    pass_type=PassType.correctness, confidence=0.95,
                    title="Shadowed return", message="Return value looks wrong.",
                )
            ]
        return []


async def test_full_review_cycle_posts_inline_and_summary():
    settings = Settings(openai_api_key="x", llm_provider="openai")
    captured = {}

    with respx.mock(base_url=API, assert_all_called=False) as mock:
        mock.get("/repos/o/r/contents/.ai-reviewer.yml").mock(
            return_value=httpx.Response(404)
        )
        mock.get("/repos/o/r/pulls/1/files").mock(
            return_value=httpx.Response(
                200,
                json=[{"filename": "app.py", "status": "modified", "patch": PATCH}],
            )
        )
        mock.get("/repos/o/r/contents/app.py").mock(
            return_value=httpx.Response(200, text=FILE_CONTENT)
        )

        def _capture(request):
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": 42})

        mock.post("/repos/o/r/pulls/1/reviews").mock(side_effect=_capture)

        client = GitHubClient("token")
        req = ReviewRequest(owner="o", repo="r", pr_number=1, head_sha="deadbeef")
        result = await run_review(client, req, settings, llm=_StubLLM())
        client.close()

    assert result.verdict == Verdict.request_changes
    assert len(result.findings) == 1

    body = captured["body"]
    assert body["event"] == "REQUEST_CHANGES"
    assert "AI PR Review" in body["body"]
    assert len(body["comments"]) == 1
    assert body["comments"][0]["path"] == "app.py"
    assert body["comments"][0]["line"] == 3
    assert body["commit_id"] == "deadbeef"


async def test_review_cycle_skips_when_only_ignored_files():
    settings = Settings(openai_api_key="x")

    with respx.mock(base_url=API, assert_all_called=False) as mock:
        mock.get("/repos/o/r/contents/.ai-reviewer.yml").mock(
            return_value=httpx.Response(404)
        )
        mock.get("/repos/o/r/pulls/1/files").mock(
            return_value=httpx.Response(
                200,
                json=[{"filename": "poetry.lock", "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"}],
            )
        )
        comment = mock.post("/repos/o/r/issues/1/comments").mock(
            return_value=httpx.Response(201, json={"id": 1})
        )

        client = GitHubClient("token")
        req = ReviewRequest(owner="o", repo="r", pr_number=1, head_sha="sha")
        result = await run_review(client, req, settings, llm=_StubLLM())
        client.close()

    assert result.verdict == Verdict.approve
    assert result.findings == []
    assert comment.called  # posted the "no reviewable changes" note
