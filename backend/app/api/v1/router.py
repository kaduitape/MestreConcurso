"""Agregador das rotas da API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import admin, auth, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
