# app/anamnese_digital/models.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

class AnamneseStatus(str, Enum):
    RASCUNHO = "rascunho"
    AGUARDANDO_ASSINATURA = "aguardando_assinatura"
    ASSINADO = "assinado"
    EXPIRADO = "expirado"

class MeioEnvio(str, Enum):
    WHATSAPP = "whatsapp"
    PRESENCIAL = "presencial"

class DadosIdentificacao(BaseModel):
    data: str
    vendedor: str
    contrato: str
    horario: str
    nome: str
    rg: str
    cpf: str
    nascimento: str
    endereco: str
    bairro: str
    complemento: str
    cep: str
    estado: str
    telefone_casa: str
    celular: str
    profissao: str
    como_conheceu: str

class SaudeGeral(BaseModel):
    q1: str
    q1_motivo: Optional[str] = ""
    q2: str
    q2_quais: Optional[str] = ""
    q3: str
    q3_mes: Optional[str] = ""
    q4: str
    q4_quais: Optional[str] = ""
    q5: str
    q6: str
    q7: str
    q8: str
    doencas: List[str] = []
    outras_doencas: Optional[str] = ""
    q11: str
    q12: str
    q13: str
    q14: str

class SaudeBucal(BaseModel):
    q15: str
    q15_motivo: Optional[str] = ""
    q16: str
    q17: str
    morde_labios: str
    q18: str
    q19: str
    dor_ouvido: str
    outros_problemas: Optional[str] = ""

class AnamneseCreate(BaseModel):
    paciente_id: int
    dependente_id: Optional[int] = None
    dados_identificacao: DadosIdentificacao
    saude_geral: SaudeGeral
    saude_bucal: SaudeBucal
    observacoes: Optional[str] = ""

class AnamneseUpdate(BaseModel):
    dados_identificacao: Optional[DadosIdentificacao] = None
    saude_geral: Optional[SaudeGeral] = None
    saude_bucal: Optional[SaudeBucal] = None
    observacoes: Optional[str] = None

class AnamneseResponse(BaseModel):
    id: int
    paciente_id: int
    dependente_id: Optional[int] = None
    status: AnamneseStatus
    dados_anamnese: Dict[str, Any]
    observacoes: Optional[str]
    created_at: datetime
    updated_at: datetime
    signed_at: Optional[datetime]
    validade_ate: Optional[datetime]
    created_by: Optional[int]
    dependente: Optional['DependenteInfo'] = None
    
    model_config = ConfigDict(from_attributes=True)


class AnamneseConsultaResumo(BaseModel):
    total: int
    rascunhos: int
    aguardando_assinatura: int
    assinadas: int
    expiradas: int


class AnamneseConsultaItem(BaseModel):
    id: int
    paciente_id: int
    dependente_id: Optional[int] = None
    beneficiario_nome: str
    titular_nome: str
    tipo_beneficiario: str
    parentesco: Optional[str] = None
    cpf_mascarado: str
    unidade: Optional[str] = None
    status: AnamneseStatus
    preenchida_em: Optional[datetime] = None
    signed_at: Optional[datetime] = None
    validade_ate: Optional[datetime] = None
    vendedor_nome: Optional[str] = None


class AnamneseConsultaResponse(BaseModel):
    total: int
    page: int
    per_page: int
    resumo: AnamneseConsultaResumo
    anamneses: List[AnamneseConsultaItem]


class AnamneseConsultaDetalhe(AnamneseConsultaItem):
    dados_anamnese: Dict[str, Any]
    dados_cadastrais: Dict[str, Any]
    dados_identificacao_mesclados: Dict[str, Any]
    observacoes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AssinaturaCreate(BaseModel):
    tipo_assinatura: str = Field(..., description="'paciente' ou 'responsavel'")
    nome_assinante: str
    cpf_assinante: str
    foto_selfie: str = Field(..., description="Imagem em base64")
    assinatura_digital: str = Field(..., description="Imagem da assinatura em base64")
    geolocalizacao: Optional[Dict[str, float]] = None

class AssinaturaResponse(BaseModel):
    id: int
    anamnese_id: int
    tipo_assinatura: str
    nome_assinante: str
    cpf_assinante: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TokenCreate(BaseModel):
    paciente_id: int
    dependente_id: Optional[int] = None
    validade_horas: int = Field(default=72, description="Validade do token em horas")

class TokenResponse(BaseModel):
    token: str
    link_publico: str
    expires_at: datetime
    
class LinkEnvio(BaseModel):
    token: str
    meio_envio: MeioEnvio
    destinatario: str = Field(..., description="Número de telefone ou email")
    mensagem_personalizada: Optional[str] = None
    unidade: Optional[str] = Field(None, description="Unidade do usuário que está enviando")

class LinkStatus(BaseModel):
    token: str
    paciente_id: int
    dependente_id: Optional[int] = None
    status: str
    created_at: datetime
    expires_at: datetime
    usado: bool
    usado_em: Optional[datetime]
    enviado_via: Optional[str]
    visualizado_em: Optional[datetime]
    preenchido_em: Optional[datetime]

# Modelos para o frontend público
class AnamnesePublicData(BaseModel):
    token: str
    paciente_nome: str
    paciente_cpf: str
    dependente_nome: Optional[str] = None
    dependente_parentesco: Optional[str] = None
    dados_preenchidos: Optional[Dict[str, Any]] = None
    pode_editar: bool = True

class AnamnesePublicSave(BaseModel):
    token: str
    dados_identificacao: DadosIdentificacao
    saude_geral: SaudeGeral
    saude_bucal: SaudeBucal
    observacoes: Optional[str] = ""

class AnamnesePublicSign(BaseModel):
    token: str
    assinatura: AssinaturaCreate

# Modelo para informações básicas do dependente
class DependenteInfo(BaseModel):
    dependente_id: int
    nome_dependente: str
    data_nascimento_dependente: Optional[str] = None
    genero_dependente: Optional[str] = None
    parentesco: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
