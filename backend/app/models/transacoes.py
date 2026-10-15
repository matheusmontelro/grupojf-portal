from pydantic import BaseModel
from typing import Optional
from datetime import date

class Transacao(BaseModel):
    id: int

    # Novos campos
    lancto: Optional[str] = None
    tipo: Optional[str] = None
    hora: Optional[str] = None
    fone1: Optional[str] = None
    fone2: Optional[str] = None
    mes: Optional[str] = None
    codigo: Optional[str] = None

    # Campos já existentes
    data: Optional[date] = None
    valor: Optional[float] = None
    unidade: Optional[str] = None
    metodo_pagamento: Optional[str] = None
    nome: Optional[str] = None
    documento: Optional[str] = None
    sistema: Optional[str] = None
    categoria: Optional[str] = None
    cpf: Optional[str] = None
    nome_crd013: Optional[str] = None
    terminal: Optional[str] = None
    usuario: Optional[str] = None

    class Config:
        orm_mode = True

class TransacaoFiltro(BaseModel):
    """ 
    (opcional) Se quiser manter um modelo de filtro, sem mudanças.
    """
    start_date: Optional[date]
    end_date: Optional[date]
    sistema: Optional[str]
    unidade: Optional[str]
    categoria: Optional[str]
    metodo_pagamento: Optional[str]
