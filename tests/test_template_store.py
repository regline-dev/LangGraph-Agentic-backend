"""양식 저장소 — 판별용 labels + 결과 양식 result_schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pdf_ingest.template_store import (
    PromptTemplate,
    build_result_schema_fill_prompt,
    has_fill_lock,
    has_result_schema,
    load_templates,
    resolve_template_prompt,
    save_template,
    soft_delete_template,
)


def test_save_and_load_with_result_schema(tmp_path: Path) -> None:
    """판별용 labels + 결과 양식 템플릿 왕복."""
    schema = {"holdings_data": {"as_of": "", "holdings": []}, "펀드": "ARKK"}
    template = PromptTemplate(
        template_id="arkk_holdings_v1",
        name="ARKK holdings",
        labels=frozenset({"Company", "Ticker", "Weight"}),
        prompt="",
        result_schema=schema,
    )
    save_template(template, store_dir=tmp_path)
    loaded = load_templates(store_dir=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].template_id == "arkk_holdings_v1"
    assert "Ticker" in loaded[0].labels
    assert loaded[0].result_schema == schema
    assert has_result_schema(loaded[0]) is True
    assert has_fill_lock(loaded[0]) is True


def test_save_allows_schema_without_prompt(tmp_path: Path) -> None:
    save_template(
        PromptTemplate(
            template_id="schema_only",
            name="스키마만",
            labels=frozenset({"부서", "매출"}),
            prompt="",
            result_schema={"부서": "", "매출": 0},
        ),
        store_dir=tmp_path,
    )
    loaded = load_templates(store_dir=tmp_path)
    assert loaded[0].prompt == ""
    assert loaded[0].result_schema == {"부서": "", "매출": 0}


def test_save_rejects_empty_schema_and_prompt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="결과 양식"):
        save_template(
            PromptTemplate(
                template_id="bad",
                name="빈",
                labels=frozenset({"부서"}),
                prompt="   ",
                result_schema=None,
            ),
            store_dir=tmp_path,
        )


def test_load_allows_label_only_seed_without_schema(tmp_path: Path) -> None:
    path = tmp_path / "label_only.json"
    path.write_text(
        json.dumps(
            {
                "template_id": "label_only",
                "name": "라벨만",
                "labels": ["부서", "매출"],
                "prompt": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded = load_templates(store_dir=tmp_path)
    assert len(loaded) == 1
    assert has_result_schema(loaded[0]) is False
    assert has_fill_lock(loaded[0]) is False


def test_build_fill_prompt_contains_schema_keys() -> None:
    text = build_result_schema_fill_prompt({"종목": ["TSLA"], "펀드": "ARKK"})
    assert "결과 양식" in text
    assert "TSLA" in text
    assert resolve_template_prompt(
        PromptTemplate(
            template_id="x",
            name="x",
            labels=frozenset({"a"}),
            prompt="옛지시문",
            result_schema={"종목": []},
        )
    ).startswith("당신은 문서에서")


def test_save_rejects_empty_labels(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="labels"):
        save_template(
            PromptTemplate(
                template_id="bad",
                name="빈지문",
                labels=frozenset(),
                prompt="무언가",
            ),
            store_dir=tmp_path,
        )


def test_soft_delete_renames_and_hides_from_load(tmp_path: Path) -> None:
    save_template(
        PromptTemplate(
            template_id="C_counsel_1",
            name="ARKK",
            labels=frozenset({"As of"}),
            prompt="",
            result_schema={"METADATA_NAME": "ARKK", "DESCRIPTION": "설명"},
        ),
        store_dir=tmp_path,
    )
    assert len(load_templates(store_dir=tmp_path)) == 1
    dest = soft_delete_template("C_counsel_1", store_dir=tmp_path)
    assert dest.name == "C_counsel_1_delete.json"
    assert dest.is_file()
    assert not (tmp_path / "C_counsel_1.json").is_file()
    assert load_templates(store_dir=tmp_path) == []
