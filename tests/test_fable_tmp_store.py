"""2차-2 — PDF tmp 경로·TTL 청소."""

import time
from pathlib import Path

from app.fable_pdf.tmp_store import cleanup_expired_tmp_pdfs, make_tmp_pdf_path


def test_make_tmp_pdf_path_includes_id_and_pdf_suffix(tmp_path: Path) -> None:
    """임시 PDF 경로에 id와 .pdf가 들어간다."""
    out = make_tmp_pdf_path(tmp_dir=tmp_path, fable_id=7)
    assert out.parent == tmp_path
    assert out.name.startswith("7_")
    assert out.suffix == ".pdf"


def test_cleanup_expired_tmp_pdfs_deletes_old_only(tmp_path: Path) -> None:
    """TTL보다 오래된 PDF만 삭제한다."""
    old_pdf = tmp_path / "1_old.pdf"
    new_pdf = tmp_path / "2_new.pdf"
    old_pdf.write_bytes(b"%PDF-old")
    new_pdf.write_bytes(b"%PDF-new")
    # mtime을 과거로 밀어 TTL 초과 상태로 만든다
    old_mtime = time.time() - (25 * 3600)
    new_mtime = time.time() - 60
    import os

    os.utime(old_pdf, (old_mtime, old_mtime))
    os.utime(new_pdf, (new_mtime, new_mtime))

    deleted = cleanup_expired_tmp_pdfs(tmp_dir=tmp_path, ttl_seconds=24 * 3600)
    assert old_pdf.name in deleted
    assert not old_pdf.exists()
    assert new_pdf.exists()
