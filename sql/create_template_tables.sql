-- 템플릿 등록 (판별 라벨 + 결과 양식 가변 필드)
-- 실행 전제: Hetzner MariaDB (로컬은 SSH 터널 127.0.0.1:3306), admin_backend_python과 같은 chatbot DB
-- ERD: Docs/20260810_템플릿등록_DB_ERD.md

CREATE TABLE IF NOT EXISTS template_registry (
    template_id_num BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '템플릿 아이디 번호',
    template_code VARCHAR(64) NOT NULL COMMENT '템플릿 코드(=template_id)',
    template_name VARCHAR(128) NOT NULL COMMENT '템플릿명 한글',
    metadata_name VARCHAR(64) NULL COMMENT 'METADATA_NAME',
    doc_type VARCHAR(1) NULL COMMENT '문서특성 A/B/C/D',
    prompt TEXT NULL COMMENT '레거시 탐색 지시문',
    doc_match_labels VARCHAR(1024) NULL COMMENT '문서 라벨 매칭 — 등록 당시 문서 구조 라벨(콤마 구분, 공백 유지)',
    is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '사용여부',
    created_by VARCHAR(50) NOT NULL COMMENT '등록자',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일',
    updated_by VARCHAR(50) NULL COMMENT '수정자',
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일',
    UNIQUE KEY uk_template_registry_code (template_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='템플릿';

CREATE TABLE IF NOT EXISTS template_fields (
    field_id_num BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '필드 아이디 번호',
    template_id_num BIGINT NOT NULL COMMENT '템플릿 아이디 번호',
    field_key VARCHAR(64) NOT NULL COMMENT '영문 키(meta_01 등, 시스템 조회용)',
    korean_label VARCHAR(64) NOT NULL COMMENT '한글 검색명(search_labels 값, 사람 검색용)',
    value VARCHAR(512) NOT NULL DEFAULT '' COMMENT '값(최초 등록 시)',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '정렬순서',
    UNIQUE KEY uk_template_fields_template_key (template_id_num, field_key),
    CONSTRAINT fk_template_fields_template
        FOREIGN KEY (template_id_num) REFERENCES template_registry (template_id_num)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='템플릿 결과 양식 가변 필드';
