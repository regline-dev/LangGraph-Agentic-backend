"""PDF 텍스트의 명시적 구조에서 메타데이터 후보를 추출한다.

문서명이나 업무별 라벨을 코드에 두지 않는다. 저장 템플릿 라벨은
``known_labels``로 받아 같은 일반 규칙에 사용한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TypedDict


class ExtractedMetadata(TypedDict):
    label: str
    value: str
    source: str


_COLON_PAIR_RE = re.compile(r"^(.{1,80}?)\s*[:：]\s*(.+)$")
_PIPE_SPLIT_RE = re.compile(r"\s*\|\s*")
_LABEL_TEXT_RE = re.compile(r"^[^\W_][\w\s()/#&+.,'’-]{0,79}$", re.UNICODE)


def extract_metadata_candidates(
    text: str,
    *,
    known_labels: Iterable[str] = (),
) -> list[ExtractedMetadata]:
    """명시적 라벨/값 후보를 원문 순서로 반환한다.

    지원 범위:
    - ``라벨: 값`` / ``라벨：값``
    - 파이프 헤더와 바로 다음 값 행
    - 설정 라벨 단독 줄 + 바로 다음 값 줄
    - 설정 라벨과 같은 줄에 이어진 값
    """
    lines = [line.strip() for line in str(text or "").splitlines()]
    configured_labels = _normalize_known_labels(known_labels)
    configured_lookup = {label.casefold(): label for label in configured_labels}
    results: list[ExtractedMetadata] = []
    seen: set[tuple[str, str]] = set()

    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue

        colon_pair = _extract_colon_pair(line)
        if colon_pair is not None:
            _append_unique(results, seen, colon_pair[0], colon_pair[1], "colon")
            index += 1
            continue

        pipe_headers = _split_pipe_cells(line)
        if pipe_headers and index + 1 < len(lines):
            pipe_values = _split_pipe_cells(lines[index + 1])
            if _is_header_value_pair(pipe_headers, pipe_values):
                for label, value in zip(pipe_headers, pipe_values):
                    _append_unique(results, seen, label, value, "pipe")
                index += 2
                continue

        exact_label = configured_lookup.get(line.casefold())
        if exact_label is not None:
            next_value = _next_nonempty_line(lines, index + 1)
            if next_value and not _is_configured_label_line(
                next_value,
                configured_labels,
            ):
                _append_unique(
                    results,
                    seen,
                    exact_label,
                    next_value,
                    "known_next_line",
                )
            index += 1
            continue

        inline_pair = _extract_known_inline_pair(line, configured_labels)
        if inline_pair is not None:
            _append_unique(
                results,
                seen,
                inline_pair[0],
                inline_pair[1],
                "known_inline",
            )

        index += 1

    return results


def extract_structure_labels(
    text: str,
    *,
    known_labels: Iterable[str] = (),
) -> frozenset[str]:
    """메타 후보와 설정 라벨 출현에서 값 없는 구조 지문을 만든다."""
    configured_labels = _normalize_known_labels(known_labels)
    labels = {
        item["label"]
        for item in extract_metadata_candidates(text, known_labels=configured_labels)
    }
    configured_lookup = {label.casefold(): label for label in configured_labels}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        exact = configured_lookup.get(line.casefold())
        if exact is not None:
            labels.add(exact)
            continue
        inline = _extract_known_inline_pair(line, configured_labels)
        if inline is not None:
            labels.add(inline[0])
    return frozenset(labels)


def _normalize_known_labels(labels: Iterable[str]) -> tuple[str, ...]:
    normalized = {
        str(label).strip()
        for label in labels or ()
        if str(label).strip()
    }
    return tuple(sorted(normalized, key=lambda item: (-len(item), item.casefold())))


def _extract_colon_pair(line: str) -> tuple[str, str] | None:
    match = _COLON_PAIR_RE.match(line)
    if match is None:
        return None
    label = match.group(1).strip()
    value = match.group(2).strip()
    if not _looks_like_label(label) or not value:
        return None
    return label, value


def _split_pipe_cells(line: str) -> list[str] | None:
    if "|" not in line:
        return None
    cells = [cell.strip() for cell in _PIPE_SPLIT_RE.split(line)]
    if len(cells) < 2 or any(not cell for cell in cells):
        return None
    return cells


def _is_header_value_pair(
    headers: list[str],
    values: list[str] | None,
) -> bool:
    if values is None or len(headers) != len(values):
        return False
    if not all(_looks_like_label(header) for header in headers):
        return False
    # 값 행과 완전히 같으면 구조가 아니라 반복 문자열로 본다.
    return any(header.casefold() != value.casefold() for header, value in zip(headers, values))


def _looks_like_label(value: str) -> bool:
    text = value.strip()
    if not text or len(text) > 80:
        return False
    if text[0] in "※*#-•":
        return False
    if text.endswith((".", "?", "!")):
        return False
    if text.count(" ") > 8:
        return False
    return bool(_LABEL_TEXT_RE.fullmatch(text))


def _next_nonempty_line(lines: list[str], start: int) -> str:
    for index in range(start, len(lines)):
        if lines[index]:
            return lines[index]
    return ""


def _is_configured_label_line(line: str, labels: tuple[str, ...]) -> bool:
    folded = line.casefold()
    return any(folded == label.casefold() for label in labels)


def _extract_known_inline_pair(
    line: str,
    labels: tuple[str, ...],
) -> tuple[str, str] | None:
    folded_line = line.casefold()
    for label in labels:
        folded_label = label.casefold()
        if not folded_line.startswith(folded_label):
            continue
        remainder = line[len(label) :].strip()
        if remainder.startswith((":","：")):
            remainder = remainder[1:].strip()
        if remainder:
            return label, remainder
    return None


def _append_unique(
    results: list[ExtractedMetadata],
    seen: set[tuple[str, str]],
    label: str,
    value: str,
    source: str,
) -> None:
    normalized_label = label.strip()
    normalized_value = value.strip()
    key = (normalized_label.casefold(), normalized_value)
    if not normalized_label or not normalized_value or key in seen:
        return
    seen.add(key)
    results.append(
        {
            "label": normalized_label,
            "value": normalized_value,
            "source": source,
        }
    )
