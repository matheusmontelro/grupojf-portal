"""create entrada taxa table

Revision ID: create_entrada_taxa_001
Revises: 
Create Date: 2025-01-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_entrada_taxa_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela de entradas/taxas
    op.create_table('entradas_taxas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('paciente_id', sa.Integer(), nullable=False),
        sa.Column('odontograma_id', sa.Integer(), nullable=True),
        sa.Column('venda_id', sa.Integer(), nullable=True),
        sa.Column('tipo', sa.String(20), nullable=False),  # 'entrada' ou 'taxa_adesao'
        sa.Column('valor', sa.Numeric(10, 2), nullable=False),
        sa.Column('forma_pagamento_id', sa.Integer(), nullable=True),
        sa.Column('forma_pagamento_nome', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),  # pendente, pago, cancelado
        sa.Column('fatura_id', sa.Integer(), nullable=True),  # ID da fatura na Delta/BemPaggo
        sa.Column('checkout_url', sa.Text(), nullable=True),
        sa.Column('data_pagamento', sa.DateTime(), nullable=True),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('unidade', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['paciente_id'], ['pacientes.paciente_id']),
        sa.ForeignKeyConstraint(['odontograma_id'], ['odontogramas.id']),
        sa.ForeignKeyConstraint(['venda_id'], ['vendas.id']),
        sa.ForeignKeyConstraint(['forma_pagamento_id'], ['forma_pagamento.id'])
    )
    
    # Criar índices
    op.create_index('idx_entradas_taxas_paciente', 'entradas_taxas', ['paciente_id'])
    op.create_index('idx_entradas_taxas_venda', 'entradas_taxas', ['venda_id'])
    op.create_index('idx_entradas_taxas_status', 'entradas_taxas', ['status'])
    op.create_index('idx_entradas_taxas_tipo', 'entradas_taxas', ['tipo'])


def downgrade():
    op.drop_index('idx_entradas_taxas_tipo')
    op.drop_index('idx_entradas_taxas_status')
    op.drop_index('idx_entradas_taxas_venda')
    op.drop_index('idx_entradas_taxas_paciente')
    op.drop_table('entradas_taxas')