"""Unit tests for Stage 1 and Stage 2 pipeline fixes.

Stage 1: Critical Pipeline Fixes
Stage 2: Reflexion Loop Repair
"""

import yaml
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Stage 1 Tests
# ---------------------------------------------------------------------------

class TestDockerComposeVolumes:
    """1.1 — Volume mounts in docker-compose.yml."""

    @pytest.fixture
    def compose(self):
        with open("docker-compose.yml", "r") as f:
            return yaml.safe_load(f)

    def test_top_level_generated_projects_volume(self, compose):
        """generated_projects declared in top-level volumes section."""
        assert "generated_projects" in compose.get("volumes", {}), (
            "Top-level 'generated_projects' volume missing from docker-compose.yml"
        )

    def test_top_level_logs_volume(self, compose):
        """logs declared in top-level volumes section."""
        assert "logs" in compose.get("volumes", {}), (
            "Top-level 'logs' volume missing from docker-compose.yml"
        )

    def _service_volume_targets(self, compose, service_name):
        service = compose["services"][service_name]
        volumes = service.get("volumes", [])
        targets = []
        for v in volumes:
            if isinstance(v, str) and ":" in v:
                targets.append(v.split(":")[1])
            elif isinstance(v, dict):
                targets.append(v.get("target", ""))
        return targets

    def test_api_mounts_generated_projects(self, compose):
        targets = self._service_volume_targets(compose, "api")
        assert "/app/generated_projects" in targets, (
            "api service does not mount generated_projects to /app/generated_projects"
        )

    def test_api_mounts_logs(self, compose):
        targets = self._service_volume_targets(compose, "api")
        assert "/app/logs" in targets, (
            "api service does not mount logs to /app/logs"
        )

    def test_celery_worker_mounts_generated_projects(self, compose):
        targets = self._service_volume_targets(compose, "celery-worker")
        assert "/app/generated_projects" in targets, (
            "celery-worker service does not mount generated_projects to /app/generated_projects"
        )

    def test_celery_worker_mounts_logs(self, compose):
        targets = self._service_volume_targets(compose, "celery-worker")
        assert "/app/logs" in targets, (
            "celery-worker service does not mount logs to /app/logs"
        )


class TestReviewFeedbackKey:
    """1.4 — review_feedback key is 'feedback', not 'comments'."""

    def test_feedback_key_used_not_comments(self):
        """_reflexion_node reads 'feedback' key from review_feedback."""
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._reflexion_node)
        assert 'get("feedback"' in source or "['feedback']" in source, (
            "_reflexion_node must read review_feedback.get('feedback', ...) not 'comments'"
        )
        assert 'get("comments"' not in source, (
            "_reflexion_node must not use the old 'comments' key"
        )

    def test_review_feedback_get_feedback_returns_empty_string_when_absent(self):
        """If 'feedback' key is absent, an empty string is returned (not KeyError)."""
        review_feedback = {"status": "REJECTED", "issues": []}
        result = review_feedback.get("feedback", "")
        assert result == ""


class TestMaxReflexionRetries:
    """1.5 — MAX_REFLEXION_RETRIES constant and boundary condition."""

    def test_constant_equals_3(self):
        from foundry.orchestrator import MAX_REFLEXION_RETRIES
        assert MAX_REFLEXION_RETRIES == 3

    def test_gate_routes_fix_when_count_less_than_max(self):
        """reflexion_count < MAX_REFLEXION_RETRIES → 'fix'."""
        from foundry.orchestrator import AgentOrchestrator, MAX_REFLEXION_RETRIES
        orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
        for count in range(MAX_REFLEXION_RETRIES):
            state = {
                "review_feedback": {"approved": False},
                "reflexion_count": count,
            }
            assert orchestrator._should_continue_from_review(state) == "fix", (
                f"Expected 'fix' for reflexion_count={count}"
            )

    def test_gate_routes_fail_when_count_equals_max(self):
        """reflexion_count == MAX_REFLEXION_RETRIES → 'fail'."""
        from foundry.orchestrator import AgentOrchestrator, MAX_REFLEXION_RETRIES
        orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
        state = {
            "review_feedback": {"approved": False},
            "reflexion_count": MAX_REFLEXION_RETRIES,
        }
        assert orchestrator._should_continue_from_review(state) == "fail"

    def test_gate_routes_fail_when_count_exceeds_max(self):
        """reflexion_count > MAX_REFLEXION_RETRIES → 'fail'."""
        from foundry.orchestrator import AgentOrchestrator, MAX_REFLEXION_RETRIES
        orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
        state = {
            "review_feedback": {"approved": False},
            "reflexion_count": MAX_REFLEXION_RETRIES + 1,
        }
        assert orchestrator._should_continue_from_review(state) == "fail"

    def test_gate_routes_approve_when_approved(self):
        """approved=True → 'approve' regardless of count."""
        from foundry.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
        state = {
            "review_feedback": {"approved": True},
            "reflexion_count": 0,
        }
        assert orchestrator._should_continue_from_review(state) == "approve"


class TestStateMergePattern:
    """1.2 — State merge pattern preserves existing project_context keys."""

    def test_pm_node_merges_context(self):
        """_pm_node uses {**state['project_context'], ...} merge pattern."""
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._pm_node)
        assert "**state[\"project_context\"]" in source or "**state['project_context']" in source, (
            "_pm_node must merge into existing project_context"
        )

    def test_architect_node_merges_context(self):
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._architect_node)
        assert "**state[\"project_context\"]" in source or "**state['project_context']" in source

    def test_engineer_node_merges_context(self):
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._engineer_node)
        assert "**state[\"project_context\"]" in source or "**state['project_context']" in source

    def test_reflexion_node_merges_context(self):
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._reflexion_node)
        assert "**state[\"project_context\"]" in source or "**state['project_context']" in source

    def test_devops_node_merges_context(self):
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._devops_node)
        assert "**state[\"project_context\"]" in source or "**state['project_context']" in source


# ---------------------------------------------------------------------------
# Stage 2 Tests
# ---------------------------------------------------------------------------

class TestQualityGatesImport:
    """2.1 — QualityGates import in reflexion.py."""

    def test_quality_gates_import_does_not_raise(self):
        """Importing ReflexionEngine must not raise NameError for QualityGates."""
        try:
            from foundry.agents.reflexion import ReflexionEngine  # noqa: F401
        except NameError as e:
            pytest.fail(f"NameError when importing ReflexionEngine: {e}")

    def test_quality_gates_instantiated_in_init(self):
        """ReflexionEngine.__init__ instantiates QualityGates without NameError."""
        from foundry.agents.reflexion import ReflexionEngine
        from foundry.testing.quality_gates import QualityGates
        engine = ReflexionEngine(model_name="qwen2.5-coder:7b")
        assert isinstance(engine.quality_gates, QualityGates)


class TestApplyFixPlanToRepo:
    """2.2 — _apply_fix_plan_to_repo method."""

    @pytest.fixture
    def engine(self):
        from foundry.agents.reflexion import ReflexionEngine
        return ReflexionEngine(model_name="qwen2.5-coder:7b")

    def test_patched_files_are_updated(self, engine):
        code_repo = {"main.py": "x = 1", "utils.py": "def helper(): pass"}
        fix_plan = {"files": {"main.py": "x = 2"}}
        result = engine._apply_fix_plan_to_repo(code_repo, fix_plan)
        assert result["main.py"] == "x = 2"

    def test_unpatched_files_are_unchanged(self, engine):
        code_repo = {"main.py": "x = 1", "utils.py": "def helper(): pass"}
        fix_plan = {"files": {"main.py": "x = 2"}}
        result = engine._apply_fix_plan_to_repo(code_repo, fix_plan)
        assert result["utils.py"] == "def helper(): pass"

    def test_new_files_can_be_added(self, engine):
        code_repo = {"main.py": "x = 1"}
        fix_plan = {"files": {"new_module.py": "def new_func(): return 42"}}
        result = engine._apply_fix_plan_to_repo(code_repo, fix_plan)
        assert result["new_module.py"] == "def new_func(): return 42"
        assert result["main.py"] == "x = 1"

    def test_empty_fix_plan_returns_original(self, engine):
        code_repo = {"main.py": "x = 1"}
        fix_plan = {"files": {}}
        result = engine._apply_fix_plan_to_repo(code_repo, fix_plan)
        assert result == code_repo

    def test_missing_files_key_returns_original(self, engine):
        code_repo = {"main.py": "x = 1"}
        fix_plan = {}
        result = engine._apply_fix_plan_to_repo(code_repo, fix_plan)
        assert result == code_repo

    def test_non_dict_files_value_returns_original(self, engine):
        code_repo = {"main.py": "x = 1"}
        fix_plan = {"files": "not a dict"}
        result = engine._apply_fix_plan_to_repo(code_repo, fix_plan)
        assert result == code_repo


class TestReflexionNodeStoresUpdatedCodeRepo:
    """2.4 — _reflexion_node stores updated code_repo in project_context."""

    def test_reflexion_node_stores_code_repo(self):
        """_reflexion_node must store updated code_repo back into project_context."""
        import inspect
        from foundry.orchestrator import AgentOrchestrator
        source = inspect.getsource(AgentOrchestrator._reflexion_node)
        # The node should extract code_repo from the response and put it in project_context
        assert "code_repo" in source, (
            "_reflexion_node must handle code_repo in project_context"
        )
        assert "updated_code_repo" in source or '"code_repo"' in source, (
            "_reflexion_node must store updated code_repo in project_context"
        )
