"""Unit tests for .github/workflows/deploy-mcp.yml CI logic.

Two pieces of behavior locked in here:

1. Env detection — branch → environment mapping. Until the kg-mcp Railway
   service exists in the prod environment, pushes to main MUST deploy to
   test (not prod); otherwise the Deploy step fails on every merge to main.
2. URL resolution — when ``railway status --json`` returns no domain (CLI
   shape drift, auth lag, fresh service), fall back to the known
   ``${SERVICE}-${ENV}.up.railway.app`` pattern. Otherwise a healthy live
   deploy gets reported as failed CI.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/deploy-mcp.yml"
MCP_CI_PATH = REPO_ROOT / ".github/workflows/mcp-ci.yml"
COMPLETENESS_TEST = (
    REPO_ROOT
    / "shrine-diet-bioactivity/lightrag/tests/test_kg_completeness_gates.py"
)
RESOLVE_SCRIPT = REPO_ROOT / "scripts/ci/resolve_railway_domain.sh"
ASSERT_DEPLOY_SCRIPT = REPO_ROOT / "scripts/ci/assert_railway_deployment.sh"


def _detect_env_run() -> str:
    """Pull the bash from the detect-environment step's ``run:`` block."""
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    return data["jobs"]["detect-environment"]["steps"][0]["run"]


def _exec_with_github_output(script: str, env: dict[str, str]) -> str:
    """Run a bash snippet with ``$GITHUB_OUTPUT`` pointing at a temp file.

    Returns the file's contents (the ``key=value`` lines the step writes).
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        out_path = f.name
    try:
        full_env = {**os.environ, **env, "GITHUB_OUTPUT": out_path}
        proc = subprocess.run(
            ["bash", "-c", script],
            env=full_env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return f"::nonzero({proc.returncode})::{proc.stderr}"
        return Path(out_path).read_text()
    finally:
        os.unlink(out_path)


# ─── Env detection ────────────────────────────────────────────────────────


class TestDetectEnv:
    def test_main_branch_routes_to_test(self):
        """Until the prod Railway env has a kg-mcp service, main→test."""
        out = _exec_with_github_output(
            _detect_env_run(),
            {
                "GH_EVENT_NAME": "push",
                "GH_REF": "refs/heads/main",
                "GH_DISPATCH_ENV": "",
            },
        )
        assert "environment=test" in out, f"main should route to test, got: {out!r}"

    def test_test_branch_routes_to_test(self):
        out = _exec_with_github_output(
            _detect_env_run(),
            {
                "GH_EVENT_NAME": "push",
                "GH_REF": "refs/heads/test",
                "GH_DISPATCH_ENV": "",
            },
        )
        assert "environment=test" in out

    def test_dev_branch_routes_to_test(self):
        out = _exec_with_github_output(
            _detect_env_run(),
            {
                "GH_EVENT_NAME": "push",
                "GH_REF": "refs/heads/dev-feature-x",
                "GH_DISPATCH_ENV": "",
            },
        )
        assert "environment=test" in out

    def test_workflow_dispatch_honors_input_prod(self):
        """Manual deploy to prod stays available — only the push-from-main
        default changes."""
        out = _exec_with_github_output(
            _detect_env_run(),
            {
                "GH_EVENT_NAME": "workflow_dispatch",
                "GH_REF": "refs/heads/main",
                "GH_DISPATCH_ENV": "prod",
            },
        )
        assert "environment=prod" in out

    def test_workflow_dispatch_honors_input_test(self):
        out = _exec_with_github_output(
            _detect_env_run(),
            {
                "GH_EVENT_NAME": "workflow_dispatch",
                "GH_REF": "refs/heads/main",
                "GH_DISPATCH_ENV": "test",
            },
        )
        assert "environment=test" in out


# ─── URL resolution ───────────────────────────────────────────────────────


class TestResolveRailwayDomain:
    """``scripts/ci/resolve_railway_domain.sh`` — reads railway status JSON
    on stdin; outputs a domain on stdout. Falls back to
    ``${service}-${env}.up.railway.app`` when JSON has no domain."""

    def _run(
        self,
        json_in: str,
        service: str = "kg-mcp",
        env: str = "test",
    ) -> tuple[int, str]:
        assert RESOLVE_SCRIPT.exists(), f"missing helper: {RESOLVE_SCRIPT}"
        proc = subprocess.run(
            ["bash", str(RESOLVE_SCRIPT), service, env],
            input=json_in,
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout.strip()

    def test_extracts_domain_from_valid_json(self):
        js = '{"service":{"serviceDomains":[{"domain":"kg-mcp-test.up.railway.app"}]}}'
        rc, out = self._run(js)
        assert rc == 0
        assert out == "kg-mcp-test.up.railway.app"

    def test_falls_back_when_json_empty(self):
        rc, out = self._run("{}", service="kg-mcp", env="test")
        assert rc == 0
        assert out == "kg-mcp-test.up.railway.app"

    def test_falls_back_when_serviceDomains_missing(self):
        rc, out = self._run('{"service":{}}', service="kg-mcp", env="test")
        assert rc == 0
        assert out == "kg-mcp-test.up.railway.app"

    def test_falls_back_when_input_is_garbage(self):
        rc, out = self._run("not json at all", service="kg-mcp", env="prod")
        assert rc == 0
        assert out == "kg-mcp-prod.up.railway.app"

    def test_uses_env_in_fallback_pattern(self):
        """Fallback respects the env arg — kg-mcp-prod for prod, etc."""
        rc, out = self._run("{}", service="kg-mcp", env="prod")
        assert rc == 0
        assert out == "kg-mcp-prod.up.railway.app"


# ─── Stale promotion guard (issue #46) ────────────────────────────────────


class TestNoStalePromotionGuard:
    """The test→main promotion guard predates the live workflow: the `test`
    branch is hundreds of commits behind main and effectively dead, so the
    guard fails on every PR for no operational reason. Lock its removal in
    so it can't quietly come back."""

    def _workflow(self) -> dict:
        return yaml.safe_load(WORKFLOW_PATH.read_text())

    def test_pr_promotion_guard_job_is_absent(self):
        jobs = self._workflow()["jobs"]
        assert "pr-promotion-guard" not in jobs, (
            "The pr-promotion-guard job has been removed (see #46) — "
            "do not reintroduce it without also reactivating the test branch."
        )

    def test_no_other_job_depends_on_promotion_guard(self):
        """Sanity: even after removal, ensure nothing in `needs:` still
        names the deleted job (which would silently fail to schedule)."""
        jobs = self._workflow()["jobs"]
        for name, body in jobs.items():
            needs = body.get("needs") or []
            if isinstance(needs, str):
                needs = [needs]
            assert "pr-promotion-guard" not in needs, (
                f"job {name!r} still has pr-promotion-guard in its needs"
            )

    def test_no_step_step_references_promotion_guard(self):
        """Catch leftover step-name strings (e.g., `name: PR Promotion Guard`).
        Stronger than the job-key check because step-name strings are easy
        to copy-paste."""
        text = WORKFLOW_PATH.read_text()
        assert "PR Promotion Guard" not in text
        assert "pr-promotion-guard" not in text


# ─── Aura gate must not silently pass on missing secrets (issue #65) ──────


class TestAuraGateRequiresSecrets:
    """The aura-data-integrity job in mcp-ci.yml previously skipped on
    missing NEO4J_* secrets and still reported SUCCESS — a false-green
    that hides a misconfigured environment. Lock in a guard step that
    fails the job when the event is push/dispatch (i.e., a trusted run
    that should have secrets) and any required secret is empty."""

    def _aura_job_run_text(self) -> str:
        data = yaml.safe_load(MCP_CI_PATH.read_text())
        job = data["jobs"]["aura-data-integrity"]
        # Join all step `run:` blocks so the guard text can live in any of them.
        return "\n".join(
            step.get("run", "")
            for step in job["steps"]
            if isinstance(step, dict)
        )

    def test_aura_job_has_secret_presence_guard(self):
        """The job must error (exit 1) when invoked on a real push/dispatch
        without the secrets being set — not just warn."""
        text = self._aura_job_run_text()
        # The fix must explicitly fail when the event isn't a PR and a
        # NEO4J_* secret is empty. We match on the documented sentinel
        # phrase so the check is robust to bash style.
        assert "exit 1" in text, (
            "aura-data-integrity job has no `exit 1` — likely still "
            "warning-only on missing secrets (see #65)."
        )
        assert "GH_EVENT_NAME" in text or "github.event_name" in text or "EVENT_NAME" in text, (
            "Guard must condition on event type so PRs from forks "
            "still skip cleanly (they have no secrets by design)."
        )


# ─── Completeness gates test must declare a marker (issue #49) ────────────


class TestCompletenessGatesHasMarker:
    """``test_kg_completeness_gates.py`` requires a 5.5 GB local SQLite DB
    that CI doesn't ship, so it must be marked ``integration`` (or
    deselected by default) — otherwise the default pytest run picks it
    up, hits a skip cascade, and inflates the noise floor of test reports.
    """

    def test_file_declares_pytestmark(self):
        text = COMPLETENESS_TEST.read_text()
        # Either ``pytestmark = pytest.mark.X`` or
        # ``pytestmark = [pytest.mark.X, ...]`` — both syntaxes are valid.
        assert "pytestmark" in text, (
            f"{COMPLETENESS_TEST.name} has no pytestmark — add the "
            "`integration` marker so default runs deselect it (see #49)."
        )
        # Must mark with one of the catalogued markers from
        # shrine-diet-bioactivity/pytest.ini. ``integration`` is the
        # appropriate one because the gates need the local KG DB.
        assert "integration" in text, (
            "completeness gates need the local KG DB → mark `integration`."
        )


# ─── deployment-advanced gate ─────────────────────────────────────────────


class TestAssertRailwayDeployment:
    """``scripts/ci/assert_railway_deployment.sh`` — the gate that replaced a
    /health poll which could not fail.

    Exit contract: 0 advanced+SUCCESS / 1 advanced+terminal-bad or unreadable
    (FAIL CLOSED) / 2 usage / 3 not-yet (unchanged id, or in progress).
    """

    def _run(self, json_in: str, prev: str = "") -> tuple[int, str]:
        assert ASSERT_DEPLOY_SCRIPT.exists(), f"missing: {ASSERT_DEPLOY_SCRIPT}"
        proc = subprocess.run(
            ["bash", str(ASSERT_DEPLOY_SCRIPT), prev],
            input=json_in, capture_output=True, text=True,
        )
        return proc.returncode, proc.stdout.strip()

    @staticmethod
    def _payload(dep_id: str, status: str, created: str = "2026-08-27T10:00:00Z") -> str:
        return json.dumps([{"id": dep_id, "status": status, "createdAt": created}])

    # ── GREEN arm ──
    def test_advanced_and_success_exits_0(self):
        rc, out = self._run(self._payload("dep-NEW", "SUCCESS"), prev="dep-OLD")
        assert rc == 0, out
        assert "dep-NEW" in out and "SUCCESS" in out

    def test_first_ever_deploy_with_no_prev_id_passes(self):
        rc, out = self._run(self._payload("dep-1", "SUCCESS"), prev="")
        assert rc == 0, out

    # ── RED arm: the bug this gate exists to catch ──
    def test_crash_at_boot_exits_1(self):
        rc, out = self._run(self._payload("dep-NEW", "CRASHED"), prev="dep-OLD")
        assert rc == 1, out
        assert "CRASHED" in out

    def test_failed_build_exits_1(self):
        rc, out = self._run(self._payload("dep-NEW", "FAILED"), prev="dep-OLD")
        assert rc == 1, out

    # ── THE STALE-READ ARM: the trap a naive "poll the status" fix walks into ──
    def test_unchanged_id_with_old_SUCCESS_does_NOT_pass(self):
        """`railway up --detach` returns before the new deployment registers.
        The newest row is then still the PREVIOUS deployment, carrying its own
        real SUCCESS. Reading it is the same stale-read defect in a new costume,
        so an unchanged id must never exit 0."""
        rc, out = self._run(self._payload("dep-OLD", "SUCCESS"), prev="dep-OLD")
        assert rc == 3, f"unchanged id must be NOT-YET (3), got {rc}: {out}"
        assert rc != 0, "a stale SUCCESS must never read as a shipped deploy"

    # ── in-progress keeps the caller polling ──
    @pytest.mark.parametrize("status", ["BUILDING", "DEPLOYING", "QUEUED", "INITIALIZING"])
    def test_in_progress_exits_3(self, status):
        rc, out = self._run(self._payload("dep-NEW", status), prev="dep-OLD")
        assert rc == 3, out

    # ── FAIL CLOSED: a gate that cannot tell must not pass ──
    @pytest.mark.parametrize(
        "payload",
        ["", "   ", "not json at all", "{}", "[]", '{"deployments":[]}',
         json.dumps([{"status": "SUCCESS"}]),                 # no id
         json.dumps([{"id": "dep-NEW"}]),                     # no status
         json.dumps([{"id": "dep-NEW", "status": "TELEPORTED"}]),  # unknown
        ],
    )
    def test_unreadable_or_unknown_fails_closed(self, payload):
        rc, _ = self._run(payload, prev="dep-OLD")
        assert rc == 1, f"must FAIL CLOSED, got {rc}"

    # ── shape tolerance (CLI JSON has drifted across versions) ──
    def test_accepts_edges_shape(self):
        js = json.dumps({"deployments": {"edges": [
            {"node": {"id": "dep-NEW", "status": "SUCCESS", "createdAt": "2026-08-27T10:00:00Z"}}]}})
        rc, out = self._run(js, prev="dep-OLD")
        assert rc == 0, out

    def test_picks_newest_by_createdAt_not_list_order(self):
        js = json.dumps([
            {"id": "dep-OLD", "status": "SUCCESS", "createdAt": "2026-06-04T10:00:00Z"},
            {"id": "dep-NEW", "status": "CRASHED", "createdAt": "2026-08-27T10:00:00Z"},
        ])
        rc, out = self._run(js, prev="dep-OLD")
        assert rc == 1, f"newest is CRASHED; stale SUCCESS must not win: {out}"

    def test_helper_is_executable(self):
        """The workflow PIPES INTO this script directly, so a missing +x bit is a
        CI-only 'Permission denied'. Every other test here runs it as
        `bash <script>`, which succeeds regardless — so the suite is structurally
        blind to this unless asserted explicitly. It shipped 644 once."""
        assert os.access(ASSERT_DEPLOY_SCRIPT, os.X_OK), (
            f"{ASSERT_DEPLOY_SCRIPT} must be executable — the workflow invokes it "
            "directly, not via `bash`"
        )

    def test_usage_error_exits_2(self):
        proc = subprocess.run(["bash", str(ASSERT_DEPLOY_SCRIPT)],
                              input="", capture_output=True, text=True)
        assert proc.returncode == 2
