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
    "exams",
    "questions",
    "alternatives",
    "question_stats",
    "question_attempts",
    "simulations",
    "simulation_questions",
    "simulation_attempts",
    "topic_incidence",
    "board_profile_metrics",
    "trap_patterns",
    "error_analyses",
    "user_priorities",
    "chat_conversations",
    "chat_messages",
    "vocabulary_terms",
    "video_resources",
    "flashcards",
    "flashcard_states",
    "flashcard_reviews",
    "game_rules",
    "gamification_profiles",
    "xp_transactions",
    "missions",
    "achievements",
    "user_achievements",
    "streak_days",
    "training_lessons",
    "training_narrations",
    "mind_maps",
}


def _sync_url() -> str:
    return settings.sqlalchemy_url.replace("+aiosqlite", "")


@pytest.fixture
def alembic_config(tmp_path: object) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)
    return config


def test_a_half_applied_migration_can_still_reach_head(alembic_config: Config) -> None:
    """O banco machucado pela corrida de deploy precisa conseguir se endireitar.

    Em MySQL o DDL não tem rollback. Quando dois ``alembic upgrade head``
    rodaram juntos em produção, um criou ``training_narrations`` e morreu antes
    de carimbar a versão — e a subida seguinte batia em "already exists" para
    sempre. Aqui esse estado é reproduzido de propósito: aplica a revisão,
    devolve o carimbo para a anterior **sem desfazer o schema**, e cobra que
    subir de novo chegue até o topo.
    """
    command.upgrade(alembic_config, "05598f0ab8c9")
    # O carimbo volta; as tabelas ficam. É exatamente o estado da produção.
    command.stamp(alembic_config, "7d0f0c1a654a")

    command.upgrade(alembic_config, "head")

    engine = create_engine(_sync_url())
    try:
        tables = set(inspect(engine).get_table_names())
        assert "training_narrations" in tables
        assert "mind_maps" in tables
    finally:
        engine.dispose()

    command.downgrade(alembic_config, "base")


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
