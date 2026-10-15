"""add user_id to dentistas table

Revision ID: add_user_id_dentistas_001
Revises: create_entrada_taxa_001
Create Date: 2025-06-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_user_id_dentistas_001'
down_revision = 'create_entrada_taxa_001'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna user_id à tabela dentistas
    op.add_column('dentistas', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Criar foreign key constraint para referenciar a tabela users
    op.create_foreign_key(
        'fk_dentistas_user_id',
        'dentistas', 
        'users',
        ['user_id'], 
        ['id'],
        ondelete='SET NULL'  # Se o usuário for deletado, o dentista permanece mas sem referência
    )
    
    # Criar índice para melhorar performance nas consultas
    op.create_index('idx_dentistas_user_id', 'dentistas', ['user_id'])


def downgrade():
    # Remover índice
    op.drop_index('idx_dentistas_user_id', 'dentistas')
    
    # Remover foreign key constraint
    op.drop_constraint('fk_dentistas_user_id', 'dentistas', type_='foreignkey')
    
    # Remover coluna
    op.drop_column('dentistas', 'user_id')