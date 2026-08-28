"""Google Cloud Vision TEXT_DETECTION. 키는 환경변수만 사용."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from collections.abc import Callable

from app.config import get_settings

VisionFn = Callable[[bytes], str]


def extract_text_google_vision(image_bytes: bytes) -> str:
    """실패 시 예외 — 호출측에서 Vision 오류 이유로 바꾼다."""
    api_key = (get_settings().google_vision_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Vision API 키가 설정되어 있지 않습니다.")
    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "TEXT_DETECTION"}],
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Vision 호출 실패: {exc}") from exc
    annotations = (
        (raw.get("responses") or [{}])[0].get("fullTextAnnotation") or {}
    )
    return str(annotations.get("text") or "").strip()
