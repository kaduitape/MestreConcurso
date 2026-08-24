"""As migrations precisam subir e descer sem intervenção manual."""

from __future__ import annotations

import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import settings

EXPECTED_TABLES = {
    "users",
    "profiles",
    "roles",
    "permissions",
    "role_permissions",
    "user_roles",
    "user_sessions",
    "auth_tokens",
    "audit_logs",
    "consent_logs",
    "exam_boards",
    "organizations",
    "competitions",
    "positions",
    "subjects",
    "topics",
    "position_subjects",
    "notices",
    "notice_files",
    "ai_providers",
    "ai_models",
    "ai_feature_bindings",
    "ai_cache_entries",
    "ai_usage",
    "board_knowledge_entries",
    "documents",
    "document_chunks",
    "notice_facts",
    "notice_sections",
    "notice_subjects",
    "notice_topics",
    "notice_events",
    "study_plans",
    "study_availability",
    "study_tasks",
    "study_sessions",
    "user_subject_progress",
}


def _sync_url() -> str:
    return settings.sqlalchemy_url.replace("+aiosqlite", "")


@pytest.fixture
def alembic_config(tmp_path: object) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)
    return config


def test_upgrade_head_then_downgrade_base(alembic_config: Config) -> None:
    # O event loop do Alembic é próprio; garante que não há loop ativo neste teste.
    assert asyncio.get_event_loop_policy() is not None

    command.upgrade(alembic_config, "head")
    engine = create_engine(_sync_url())
    try:
        tables = set(inspect(engine).get_table_names())
        assert tables >= EXPECTED_TABLES

        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        assert {"email", "password_hash", "status", "public_id", "deleted_at"} <= columns
    finally:
        engine.dispose()

    command.downgrade(alembic_config, "base")
    engine = create_engine(_sync_url())
    try:
        remaining = set(inspect(engine).get_table_names())
        assert not (EXPECTED_TABLES & remaining)
    finally:
        engine.dispose()
