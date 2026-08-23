"""Tipos de coluna portáveis entre MySQL (produção) e SQLite (testes)."""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Integer, String, Text
from sqlalchemy.dialects import mysql

# Texto longo: LONGTEXT no MySQL, TEXT no SQLite.
LongText = Text().with_variant(mysql.LONGTEXT(), "mysql")
MediumText = Text().with_variant(mysql.MEDIUMTEXT(), "mysql")

# JSON nativo nos dois dialetos.
JsonType = JSON().with_variant(mysql.JSON(), "mysql")

# ULID público (26 chars) e hashes hexadecimais.
PublicId = String(26)
Sha256Hex = String(64)

# SQLite só auto-incrementa colunas INTEGER; no MySQL a PK continua BIGINT.
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")
