"""MBTI 설정·변경 안내 명령."""

from app.metrics.mbti_commands import try_handle_mbti_command
from app.metrics.memory import FableSessionMemory


def test_set_mbti_saves_to_memory() -> None:
    memory = FableSessionMemory()
    result = try_handle_mbti_command(
        "MBTI : infp",
        session_id="s1",
        memory=memory,
    )
    assert result is not None
    assert "INFP" in result["answer"]
    assert memory.get_mbti("s1") == "INFP"
    assert result["mbti"] == "INFP"


def test_help_when_mbti_set() -> None:
    memory = FableSessionMemory()
    memory.set_mbti("s1", "INFP")
    result = try_handle_mbti_command("mbti 변경", session_id="s1", memory=memory)
    assert result is not None
    assert "수정 예시" in result["answer"]
    assert "INFP" in result["answer"]


def test_help_설정변경_without_mbti() -> None:
    memory = FableSessionMemory()
    result = try_handle_mbti_command("설정변경", session_id="s1", memory=memory)
    assert result is not None
    assert "입력 예시" in result["answer"]


def test_non_command_returns_none() -> None:
    memory = FableSessionMemory()
    assert (
        try_handle_mbti_command("늑대와 어린양 원문은", session_id="s1", memory=memory)
        is None
    )


def test_help_intent_variants_without_listing_each() -> None:
    """목록에 없는 자연어 변형도 mbti+변경의도로 안내."""
    memory = FableSessionMemory()
    phrases = (
        "mbti로 바꿔 보려면",
        "mbti 수정",
        "mbti 좀 바꿀래",
        "mbti 변경하고싶은데",
        "MBTI 설정하고 싶어",
        "유형 바꾸고 싶어",
    )
    for phrase in phrases:
        result = try_handle_mbti_command(phrase, session_id="s1", memory=memory)
        assert result is not None, phrase
        assert "입력 예시" in result["answer"] or "수정 예시" in result["answer"], phrase


def test_help_does_not_catch_유형별_해석() -> None:
    """유형별 해석은 변경 안내가 아님 → None (verbatim이 처리)."""
    memory = FableSessionMemory()
    assert (
        try_handle_mbti_command("박쥐와 족제비 유형별 해석", session_id="s1", memory=memory)
        is None
    )
    assert try_handle_mbti_command("재해석", session_id="s1", memory=memory) is None


def test_standalone_mbti_without_intent_returns_none() -> None:
    """동사 없는 단독 mbti는 vague 되묻기로 넘김."""
    memory = FableSessionMemory()
    assert try_handle_mbti_command("mbti", session_id="s1", memory=memory) is None
