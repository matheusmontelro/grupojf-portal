#!/usr/bin/env python3
"""
Migração para criar a tabela funcoes_dentista
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database.db import SessionLocal
from sqlalchemy import text

def create_funcoes_dentista_table():
    db = SessionLocal()
    try:
        print("Criando tabela funcoes_dentista...")
        
        # Criar a tabela
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS funcoes_dentista (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL UNIQUE,
                descricao TEXT,
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """))
        
        print("Tabela funcoes_dentista criada com sucesso!")
        
        # Buscar funções existentes da tabela dentistas
        print("Buscando funções existentes na tabela dentistas...")
        result = db.execute(text("""
            SELECT DISTINCT funcao 
            FROM dentistas 
            WHERE funcao IS NOT NULL AND funcao != '' 
            ORDER BY funcao;
        """))
        funcoes_existentes = result.fetchall()
        
        print(f"Encontradas {len(funcoes_existentes)} funções únicas")
        
        # Inserir as funções existentes na nova tabela
        for funcao in funcoes_existentes:
            nome_funcao = funcao[0]
            print(f"Inserindo função: {nome_funcao}")
            
            # Verificar se já existe
            check_result = db.execute(text("""
                SELECT COUNT(*) FROM funcoes_dentista WHERE nome = :nome
            """), {"nome": nome_funcao})
            
            if check_result.scalar() == 0:
                db.execute(text("""
                    INSERT INTO funcoes_dentista (nome, descricao, ativo, created_at, updated_at)
                    VALUES (:nome, :descricao, TRUE, NOW(), NOW())
                """), {
                    "nome": nome_funcao,
                    "descricao": f"Função {nome_funcao} - migrada automaticamente da tabela dentistas"
                })
        
        db.commit()
        print("✅ Migração concluída com sucesso!")
        print("Funções inseridas na tabela funcoes_dentista:")
        
        # Mostrar resultado final
        result = db.execute(text("SELECT id, nome FROM funcoes_dentista ORDER BY nome"))
        funcoes_final = result.fetchall()
        for funcao in funcoes_final:
            print(f"  - ID {funcao[0]}: {funcao[1]}")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Erro durante a migração: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_funcoes_dentista_table()
