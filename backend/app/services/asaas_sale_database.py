"""Conexao PostgreSQL exclusiva do fluxo de vendas Asaas.

Este modulo le somente o ambiente do processo. Ele nao carrega o `.env` global
e nao depende da configuracao de banco usada pelos fluxos legados.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg2


class AsaasSaleDatabaseConfigError(RuntimeError):
    """Configuracao dedicada de banco ausente ou invalida."""


def _database_config() -> dict[str, Any]:
    password = str(os.getenv("ASAAS_SALES_DB_PASSWORD", ""))
    required = {
        "dbname": str(os.getenv("ASAAS_SALES_DB_NAME", "")).strip(),
        "user": str(os.getenv("ASAAS_SALES_DB_USER", "")).strip(),
        "password": password,
    }
    if any(not value for value in required.values()) or not password.strip():
        raise AsaasSaleDatabaseConfigError(
            "Configuracao dedicada do banco de vendas Asaas incompleta."
        )

    host = str(os.getenv("ASAAS_SALES_DB_HOST", "localhost")).strip()
    raw_port = str(os.getenv("ASAAS_SALES_DB_PORT", "5432")).strip()
    if not host:
        raise AsaasSaleDatabaseConfigError(
            "Host do banco de vendas Asaas invalido."
        )
    try:
        port = int(raw_port)
    except ValueError:
        raise AsaasSaleDatabaseConfigError(
            "Porta do banco de vendas Asaas invalida."
        ) from None
    if not 1 <= port <= 65535:
        raise AsaasSaleDatabaseConfigError(
            "Porta do banco de vendas Asaas invalida."
        )
    return {
        "host": host,
        "port": port,
        **required,
        "connect_timeout": 10,
        "application_name": "grupojf-asaas-sales",
    }


class DatabaseConnection:
    """Transacao curta e fail-closed para a inbox/outbox de vendas Asaas."""

    def __init__(self, *, read_only: bool = False) -> None:
        self.conn = None
        self.read_only = read_only

    def __enter__(self):
        self.conn = psycopg2.connect(**_database_config())
        if self.read_only:
            try:
                self.conn.set_session(readonly=True)
            except Exception:
                self.conn.close()
                self.conn = None
                raise
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.conn is None:
            return
        try:
            if self.read_only:
                self.conn.rollback()
            elif exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
            self.conn = None
