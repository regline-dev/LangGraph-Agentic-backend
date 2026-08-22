"""type_code ↔ METADATA_NAME 정규화·PDF 스탬프.

PDF 필수 스탬프는 METADATA_NAME(= type_code) 하나.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, create_string_object

# type_타임스탬프 형식 금지 (구 ADD 방식)
_TIMESTAMP_TYPE_RE = re.compile(r"^TYPE_\d{10,}$", re.IGNORECASE)
# 정규화 후 허용: 영문대문자·숫자·밑줄·한글
_TYPE_CODE_BODY_RE = re.compile(r"^[A-Z0-9_\uAC00-\uD7A3]+$")


@dataclass(frozen=True)
class TypeCodeValidation:
    ok: bool
    code: str = ""
    message: str = ""


def normalize_type_code(raw: str | None) -> str:
    """METADATA_NAME과 동일: 공백 제거 + ASCII 대문자화."""
    if raw is None:
        return ""
    return "".join(str(raw).split()).upper()


def validate_type_code(raw: str | None) -> TypeCodeValidation:
    """type_code 규격 검사. 통과 시 정규화된 code 반환."""
    code = normalize_type_code(raw)
    if not code:
        return TypeCodeValidation(ok=False, message="type_code가 비어 있습니다.")
    if len(code) > 64:
        return TypeCodeValidation(ok=False, message="type_code는 64자 이하여야 합니다.")
    if _TIMESTAMP_TYPE_RE.match(code):
        return TypeCodeValidation(
            ok=False,
            message="type_코드에 타임스탬프 형식(type_숫자)은 사용할 수 없습니다.",
        )
    if not _TYPE_CODE_BODY_RE.match(code):
        return TypeCodeValidation(
            ok=False,
            message="type_code는 영문·숫자·밑줄·한글만 사용할 수 있습니다.",
        )
    return TypeCodeValidation(ok=True, code=code)


def stamp_metadata_name_on_pdf(pdf_path: str, type_code: str | None) -> str:
    """
    생성된 PDF Info에 /METADATA_NAME 을 기록한다.
    반환: 정규화된 METADATA_NAME 값.
    (이미 DB에 있는 구 type_타임스탬프 코드도 스탬프는 허용)
    """
    name = normalize_type_code(type_code)
    if not name:
        raise ValueError("type_code가 비어 있습니다.")
    if len(name) > 64:
        raise ValueError("type_code는 64자 이하여야 합니다.")
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF 없음: {pdf_path}")

    reader = PdfReader(str(path))
    writer = PdfWriter()
    writer.append(reader)

    meta_dict: dict = {}
    if reader.metadata:
        try:
            meta_dict.update(dict(reader.metadata))
        except Exception:
            pass
    meta_dict[NameObject("/METADATA_NAME")] = create_string_object(name)
    meta_dict[NameObject("/Subject")] = create_string_object(f"METADATA_NAME={name}")
    writer.add_metadata(meta_dict)

    tmp = path.with_suffix(".stamp.tmp.pdf")
    try:
        with tmp.open("wb") as fh:
            writer.write(fh)
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    return name
