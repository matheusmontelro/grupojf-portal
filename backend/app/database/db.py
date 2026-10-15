import logging
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.security.passwords import hash_password, verify_password


logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# Configuração da conexão com o banco de dados
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "dbname": os.getenv("DB_NAME", "grupojfdb"),
    "user": os.getenv("DB_USER", "grupojf_user"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": os.getenv("DB_PORT", "5432"),
}

# URL de conexão do SQLAlchemy
SQLALCHEMY_DATABASE_URL = URL.create(
    "postgresql+psycopg2",
    username=DB_CONFIG["user"],
    password=DB_CONFIG["password"],
    host=DB_CONFIG["host"],
    port=int(DB_CONFIG["port"]),
    database=DB_CONFIG["dbname"],
)

# Criar a engine do SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Criar a fábrica de sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Criar a classe Base para os modelos
Base = declarative_base()

# Função para obter a sessão do banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Classe para conexão direta com o PostgreSQL (para manter compatibilidade)
class DatabaseConnection:
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        # Conectar ao banco quando entrar no contexto "with"
        self.conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"]
        )
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Fechar a conexão ao sair do contexto "with"
        if self.conn:
            if exc_type is None:
                # Sem exceção, commit
                self.conn.commit()
            else:
                # Exceção, rollback
                self.conn.rollback()
            self.conn.close()
            self.conn = None

# Função para verificar credenciais de usuário (autenticação)
def verify_user(email, senha):
    """
    Verifica se um usuário existe com o email e senha fornecidos.
    Retorna o usuário se as credenciais são válidas, ou None caso contrário.
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, nome, email, role, unidade, foto_path, created_at, senha
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
            """, (email.strip().casefold(),))
            row = cursor.fetchone()

        if not row:
            return None

        is_valid, needs_rehash = verify_password(senha, row[7])
        if not is_valid:
            return None

        if needs_rehash:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET senha = %s WHERE id = %s",
                    (hash_password(senha, enforce_policy=False), row[0]),
                )

        # Retornar dados do usuário em formato de dicionário
        return {
            "id": row[0],
            "nome": row[1],
            "email": row[2],
            "role": row[3],
            "unidade": row[4],
            "foto_path": row[5],
            "created_at": row[6],
            "auth_version": get_auth_version(row[2]) or 0,
        }
    except Exception as exc:
        logger.error("Erro ao verificar credenciais (%s)", type(exc).__name__)
        return None


def get_auth_version(email: str):
    """Retorna a versão de sessão; aceita schema legado até a migration ser aplicada."""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT auth_version FROM users WHERE LOWER(email) = %s LIMIT 1",
                (email.strip().casefold(),),
            )
            row = cursor.fetchone()
        return row[0] if row else None
    except psycopg2.errors.UndefinedColumn:
        return 0


def get_user_id_by_email(email: str):
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE LOWER(email) = %s LIMIT 1",
            (email.strip().casefold(),),
        )
        row = cursor.fetchone()
    return row[0] if row else None
