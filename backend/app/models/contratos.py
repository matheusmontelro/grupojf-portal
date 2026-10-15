# models/contratos.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

#
# Classe base com todos os campos do banco para 'contratos'.
#
class ContratoBase(BaseModel):
    paciente_id: int = Field(..., description="FK para o paciente associado.")
    tipo_contrato: str = Field(..., description="Tipo de contrato (ex: 'ORTODONTIA', 'ODONTOLÓGICO', etc.).")
    status: str = Field("ativo", description="Status do contrato (ex: 'ativo', 'cancelado').")
    data_cancelamento: Optional[datetime] = Field(None, description="Momento do cancelamento, se houver.")
    dependente_id: Optional[int] = Field(None, description="ID do dependente quando o contrato é para tratamento de um dependente.")
    forma_pagamento_id: Optional[int] = Field(None, description="ID da forma de pagamento para este contrato.")

#
# Para criar um novo contrato.
#
class ContratoCreate(ContratoBase):
    pass

#
# Para leitura (retorno ao front).
# Inclui o 'contrato_id' e 'data_criacao'.
#
class ContratoRead(ContratoBase):
    contrato_id: int
    data_criacao: datetime

    class Config:
        orm_mode = True
