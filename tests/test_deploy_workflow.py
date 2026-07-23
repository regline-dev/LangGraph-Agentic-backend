"""배포 자동화 워크플로 계약 (파일 존재·핵심 키)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-hetzner.yml"


def test_deploy_workflow_exists() -> None:
    assert WORKFLOW.is_file(), "deploy-hetzner.yml 이 있어야 한다"


def test_deploy_workflow_targets_langgraph_agentic_and_health() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "langgraph_agentic" in text
    assert "docker compose" in text or "docker-compose" in text
    assert "/health" in text
    assert "HETZNER_HOST" in text
    assert "HETZNER_USER" in text
    assert "HETZNER_SSH_KEY" in text
    assert "workflow_dispatch" in text
    assert "branches: [main]" in text or "branches:\n      - main" in text
