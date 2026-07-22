"""한글 PDF/차트용 폰트 경로 탐색 (Linux Nanum · Windows 맑은고딕)."""

from __future__ import annotations

from pathlib import Path

# Docker(apt fonts-nanum) → 로컬 Windows → 일반 DejaVu 순
_CANDIDATE_REGULAR = (
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
_CANDIDATE_BOLD = (
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def resolve_korean_font_paths() -> tuple[str, str]:
    """
    (regular, bold) TTF 경로.
    둘 다 없으면 FileNotFoundError.
    bold가 없으면 regular를 재사용한다.
    """
    regular: str | None = None
    for candidate in _CANDIDATE_REGULAR:
        if Path(candidate).is_file():
            regular = candidate
            break
    if regular is None:
        raise FileNotFoundError(
            "한글 폰트 TTF를 찾지 못했습니다. "
            "Docker는 fonts-nanum, Windows는 맑은 고딕이 필요합니다."
        )

    bold = regular
    for candidate in _CANDIDATE_BOLD:
        if Path(candidate).is_file():
            bold = candidate
            break
    return regular, bold
