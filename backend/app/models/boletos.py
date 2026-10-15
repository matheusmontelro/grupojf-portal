# app/models/boletos.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

#
# Este modelo é usado para CRIAR boletos via Bempaggo.
# Ele contém todos os campos que vêm do form (nome, cpf, endereço, etc.)
#
class BoletoCreateFull(BaseModel):
    # Dados do cliente
    nome_cliente: str
    cpf_cnpj: str
    email: Optional[str]
    birthdate: Optional[datetime]
    phone_country_code: str = Field(..., description="Código do país, ex: '55'")
    phone_area_code: str = Field(..., description="DDD, ex: '21'")
    phone_number: str = Field(..., description="Número de telefone, ex: '999999999'")

    # Endereço
    street: str
    street_number: str
    neighborhood: str
    city: str
    state: str
    zip_code: str

    # Valor e parcelas
    valor_reais: float
    num_parcelas: int = 1
    days_until_due: int = 30  # Dias até o vencimento da primeira parcela

    # Dependente menor de idade
    is_minor_dependent: bool = False
    dependent_name: Optional[str]

    # Unidade/Clínica (para selecionar o token correto e também salvar no DB)
    unidade: str = "Nova Iguaçu 1"

    # Caso queira repassar instruções personalizadas (opcional)
    instrucoes_padrao: Optional[str] = "Não receber após o vencimento"

    # Novo campo para relacionar o boleto a um contrato específico (caso utilize essa lógica)
    contrato_id: Optional[int] = Field(
        None, description="FK para a tabela contratos (caso o boleto seja vinculado a um contrato)."
    )

    criado_por: Optional[str] = Field(
        default=None,
        description="Nome do usuário que criou o boleto"
    )


#
# Para retornar a lista de boletos criados ao front, podemos usar esse modelo
#
class BoletoCreatedItem(BaseModel):
    parcela: int
    total_parcelas: int
    id: int
    status: str
    boleto_url: str
    digitable_line: str
    bar_code: str
    message: str  # Mensagem de sucesso ou erro na hora de salvar no DB


#
# Para listagem e leitura de boletos já salvos no banco
#
class BoletoRead(BaseModel):
    id: int
    nome_cliente: str
    cpf_cnpj: str
    telefone: Optional[str]
    endereco: Optional[str]
    valor: float
    data_vencimento: datetime
    boleto_url: Optional[str]
    linha_digitavel: Optional[str]
    codigo_barras: Optional[str]
    status: str
    data_geracao: datetime
    unidade: str
    charge_id: Optional[str]
    criado_por: str
    uuid: str
    instrucoes: Optional[str]
    dependent_name: Optional[str]
    is_minor: bool
    order_reference: str
    metodo_pagamento: Optional[str]
    numero_parcela: int
    total_parcelas: int
    # Novo campo para refletir o FK no banco
    contrato_id: Optional[int] = Field(
        None, description="FK para a tabela contratos (caso o boleto seja vinculado a um contrato)."
    )


#
# Para atualizar campos de um boleto existente no banco
#
class BoletoUpdate(BaseModel):
    nome_cliente: Optional[str]
    cpf_cnpj: Optional[str]
    telefone: Optional[str]
    endereco: Optional[str]
    valor: Optional[float]
    data_vencimento: Optional[datetime]
    boleto_url: Optional[str]
    linha_digitavel: Optional[str]
    codigo_barras: Optional[str]
    status: Optional[str]
    unidade: Optional[str]
    charge_id: Optional[str]
    criado_por: Optional[str]
    uuid: Optional[str]
    instrucoes: Optional[str]
    dependent_name: Optional[str]
    is_minor: Optional[bool]
    order_reference: Optional[str]
    metodo_pagamento: Optional[str]
    numero_parcela: Optional[int]
    total_parcelas: Optional[int]
    # Novo campo para atualizar o FK do contrato, se necessário
    contrato_id: Optional[int] = Field(
        None, description="FK para a tabela contratos (caso o boleto seja vinculado a um contrato)."
    )
