# app/models/pacientes.py
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime, date

class PacienteBase(BaseModel):
    nome_paciente: str = Field(..., description="Nome completo do paciente (ou responsável).")
    cpf_cnpj: str = Field(..., description="CPF ou CNPJ do paciente.")
    email: Optional[str] = Field(None, description="E-mail do paciente.")
    data_nascimento: Optional[date] = Field(None, description="Data de nascimento do paciente.")
    is_minor: bool = Field(False, description="Indica se o paciente é menor de idade.")
    responsavel_id: Optional[int] = Field(None, description="FK para outro paciente, caso este seja dependente.")
    phone_country_code: Optional[str] = Field(None, description="Código do país do telefone (ex: '55').")
    phone_area_code: Optional[str] = Field(None, description="DDD do telefone (ex: '21').")
    phone_number: Optional[str] = Field(None, description="Número de telefone (ex: '999999999').")
    street: Optional[str] = Field(None, description="Logradouro.")
    street_number: Optional[str] = Field(None, description="Número do endereço.")
    line_two: Optional[str] = Field(None, description="Complemento do endereço.")
    neighborhood: Optional[str] = Field(None, description="Bairro.")
    city: Optional[str] = Field(None, description="Cidade.")
    state: Optional[str] = Field(None, description="Estado (UF).")
    zip_code: Optional[str] = Field(None, description="CEP.")
    unidade: Optional[str] = Field(None, description="Unidade ou clínica associada ao paciente.")
    # --- NOVOS CAMPOS ADICIONADOS ---
    rg_ie: Optional[str] = Field(None, max_length=20, description="RG ou Inscrição Estadual")
    genero: Optional[str] = Field(None, max_length=20, description="Gênero do paciente")
    observacoes: Optional[str] = Field(None, description="Observações gerais sobre o paciente")
    midia_origem: Optional[str] = Field(None, max_length=50, description="Fonte de origem do paciente: Meta Ads, Indicação, Google, Fachada, etc.")
    street_id: Optional[int] = Field(None, description="ID do vendedor street que originou o cadastro")
    # ---------------------------------

class DadosDependenteModel(BaseModel):
    nome_dependente: str = Field(..., description="Nome completo do dependente.")
    data_nascimento_dependente: Optional[date] = Field(None, description="Data de nascimento do dependente.")
    genero_dependente: Optional[str] = Field(None, max_length=20, description="Gênero do dependente.")
    parentesco: Optional[str] = Field(None, max_length=50, description="Parentesco com o responsável (ex: Filho(a)).")
    observacoes_dependente: Optional[str] = Field(None, description="Observações sobre o dependente.")

    @model_validator(mode='after')
    def validar_campos_obrigatorios(self):
        obrigatorios = {
            'nome_dependente': self.nome_dependente,
            'data_nascimento_dependente': self.data_nascimento_dependente,
            'genero_dependente': self.genero_dependente,
            'parentesco': self.parentesco,
        }
        ausentes = [campo for campo, valor in obrigatorios.items() if valor is None or (isinstance(valor, str) and not valor.strip())]
        if ausentes:
            raise ValueError(f"Campos obrigatórios do dependente ausentes: {', '.join(ausentes)}")
        return self

class DependenteRead(DadosDependenteModel):
    dependente_id: int
    responsavel_paciente_id: int
    ativo: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DependenteUpdate(BaseModel):
    nome_dependente: Optional[str] = Field(None, description="Nome completo do dependente.")
    data_nascimento_dependente: Optional[date] = Field(None, description="Data de nascimento do dependente.")
    genero_dependente: Optional[str] = Field(None, max_length=20, description="Gênero do dependente.")
    parentesco: Optional[str] = Field(None, max_length=50, description="Parentesco com o responsável (ex: Filho(a)).")
    observacoes_dependente: Optional[str] = Field(None, description="Observações sobre o dependente.")
    ativo: Optional[bool] = Field(None, description="Status ativo do dependente.")

    @model_validator(mode='after')
    def validar_dados_quando_editados(self):
        campos = ('nome_dependente', 'data_nascimento_dependente', 'genero_dependente', 'parentesco')
        if not any(campo in self.model_fields_set for campo in campos):
            return self
        ausentes = [
            campo for campo in campos
            if getattr(self, campo) is None or (
                isinstance(getattr(self, campo), str) and not getattr(self, campo).strip()
            )
        ]
        if ausentes:
            raise ValueError(f"Campos obrigatórios do dependente ausentes: {', '.join(ausentes)}")
        return self

class PacienteCreate(PacienteBase):
    # Herda todos os campos de PacienteBase, incluindo os novos
    is_cadastro_dependente: bool = Field(False, description="Indica se o cadastro é para um dependente vinculado a um responsável.")
    dados_dependente: Optional[DadosDependenteModel] = Field(None, description="Dados do dependente, se is_cadastro_dependente for True.")

class PacienteRead(PacienteBase):
    paciente_id: int
    created_at: datetime
    updated_at: datetime
    # Os campos rg_ie, genero, observacoes, midia_origem já são herdados como Optional de PacienteBase

    class Config:
        from_attributes = True # Pydantic v2 (substitui orm_mode)
