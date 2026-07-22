"""2차-2 — 우화 ID 시퀀스 파일 채번."""

from pathlib import Path

from app.fable_pdf.id_sequence import next_fable_id


def test_next_fable_id_starts_at_one(tmp_path: Path) -> None:
    """시퀀스 파일이 없으면 1부터 시작한다."""
    seq_path = tmp_path / "fable_id_seq.txt"
    assert next_fable_id(seq_path) == 1
    assert seq_path.read_text(encoding="utf-8").strip() == "1"


def test_next_fable_id_increments(tmp_path: Path) -> None:
    """연속 호출 시 번호가 1씩 증가한다."""
    seq_path = tmp_path / "fable_id_seq.txt"
    assert next_fable_id(seq_path) == 1
    assert next_fable_id(seq_path) == 2
    assert next_fable_id(seq_path) == 3
