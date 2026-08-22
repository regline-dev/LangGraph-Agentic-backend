-- 벡터화 문서 버전 관리 (문서 정체성 + 버전 이력)
-- 실행 전제: Hetzner MariaDB (로컬은 SSH 터널 127.0.0.1:3306), admin_backend_python과 같은 chatbot DB
-- 계획: Docs/20260814_벡터화_문서버전관리_계획.md (2026-08-10 템플릿등록 DB ERD 부록의 template_documents 설계를 문서/버전 2테이블로 확장)

CREATE TABLE IF NOT EXISTS documents (
    document_id_num BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '문서 아이디 번호',
    template_id_num BIGINT NULL COMMENT '벡터화 당시 매칭된 템플릿(참고용 — 판단 로직은 collection+source_file만 씀)',
    collection VARCHAR(64) NOT NULL COMMENT '컬렉션명',
    source_file VARCHAR(255) NOT NULL COMMENT '파일명 — 최초 등록 시 파일명, 식별 조회 키',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '최초 등록시각',
    UNIQUE KEY uk_documents_collection_source (collection, source_file),
    CONSTRAINT fk_documents_template
        FOREIGN KEY (template_id_num) REFERENCES template_registry (template_id_num)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='벡터화 문서 — 정체성(파일당 1행)';

CREATE TABLE IF NOT EXISTS document_versions (
    document_version_id_num BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '버전 아이디 번호',
    document_id_num BIGINT NOT NULL COMMENT '문서 아이디 번호',
    version INT NOT NULL COMMENT '버전 번호(1부터 증가)',
    content_hash VARCHAR(64) NOT NULL COMMENT '콘텐츠 해시(SHA256)',
    is_current TINYINT(1) NOT NULL DEFAULT 1 COMMENT '최신 여부 — 새 버전 생기면 이전 행은 0',
    title VARCHAR(255) NULL COMMENT '제목',
    page_count INT NULL COMMENT '총페이지',
    char_count INT NULL COMMENT '총글자수',
    indexed INT NULL COMMENT '적재청크수',
    pdf_loader VARCHAR(32) NULL COMMENT 'PDF로더',
    chunk_size INT NULL COMMENT '청크크기',
    chunk_overlap INT NULL COMMENT '청크오버랩',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성시각',
    UNIQUE KEY uk_document_versions_doc_version (document_id_num, version),
    CONSTRAINT fk_document_versions_document
        FOREIGN KEY (document_id_num) REFERENCES documents (document_id_num)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='벡터화 문서 버전 — 벡터화 실행마다 1행, 이력 전부 보존';
