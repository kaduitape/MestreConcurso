"""Agregador das rotas da API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    admin,
    admin_ai,
    admin_catalog,
    admin_notices,
    analytics,
    auth,
    billing,
    catalog,
    flashcards,
    game,
    intelligence,
    notice_analysis,
    questions,
    study,
    training,
    tutor,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(catalog.router)
api_router.include_router(study.router)
api_router.include_router(training.training_router)
api_router.include_router(questions.router)
api_router.include_router(intelligence.router)
api_router.include_router(tutor.router)
api_router.include_router(flashcards.router)
api_router.include_router(game.router)
api_router.include_router(analytics.router)
api_router.include_router(billing.router)
api_router.include_router(admin.router)
api_router.include_router(admin_ai.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_notices.router)
api_router.include_router(training.admin_router)
api_router.include_router(notice_analysis.router)
