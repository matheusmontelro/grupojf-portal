# digital_contracts/service.py
import json
import uuid
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from ..database.db import DatabaseConnection
from .signature_processor_simple import SignatureProcessor
from .template_manager import template_manager
from .image_optimizer_simple import ImageOptimizer

logger = logging.getLogger("digital_contracts_service")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://api.exemplo.com")

class DigitalContractService:
    
    def create_contract(self, paciente_id: int, odontograma_id: int, vendedor_nome: str = None, forma_pagamento: str = None, dia_vencimento: int = None, qtd_parcelas: int = None, dependente_id: int = None, valor_total: float = None) -> str:
        """
        Cria contrato e retorna link para WhatsApp
        """
        logger.info(
            "Criação de contrato iniciada (paciente_id=%s, odontograma_id=%s, dependente_id=%s)",
            paciente_id,
            odontograma_id,
            dependente_id,
        )
        
        try:
            # 1. Verificar se já existe um contrato para este odontograma
            logger.info("🔍 Verificando se já existe contrato...")
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, access_token, status, expires_at
                    FROM digital_contracts
                    WHERE odontograma_id = %s
                    AND status NOT IN ('expired', 'cancelled')
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (odontograma_id,))
                
                existing_contract = cursor.fetchone()
                if existing_contract:
                    contract_id, access_token, status, expires_at = existing_contract
                    logger.info(f"✅ Contrato existente encontrado: ID={contract_id}, Status={status}, Expira={expires_at}")
                    
                    # Se o contrato já foi assinado, retornar erro
                    if status == 'signed':
                        raise Exception("Já existe um contrato assinado para este odontograma")
                    
                    # Verificar se o contrato ainda está válido (não expirado)
                    now = datetime.now(timezone.utc)
                    if expires_at and expires_at.replace(tzinfo=timezone.utc) > now:
                        # Contrato ainda válido, retornar o link existente
                        link = f"{PUBLIC_BASE_URL}/contrato/{access_token}"
                        logger.info("Contrato existente ainda válido (id=%s)", contract_id)
                        return link
                    else:
                        logger.warning(f"⚠️ Contrato existente ID={contract_id} está expirado. Criando novo contrato...")
            
            # 2. Preparar dados do contrato incluindo vendedor e forma de pagamento
            contract_data = {}
            if vendedor_nome:
                contract_data['vendedor_nome'] = vendedor_nome
                logger.info("Vendedor incluído nos dados internos do contrato")
            if forma_pagamento:
                contract_data['forma_pagamento'] = forma_pagamento
                logger.info("Forma de pagamento incluída nos dados internos do contrato")
            
            if dia_vencimento is not None:
                contract_data['dia_vencimento'] = dia_vencimento
                logger.info("Dia de vencimento incluído nos dados internos do contrato")
            
            if qtd_parcelas is not None:
                contract_data['qtd_parcelas'] = qtd_parcelas
                logger.info("Quantidade de parcelas incluída nos dados internos do contrato")
            
            if valor_total is not None:
                contract_data['valor_total'] = valor_total
                logger.info("Valor total incluído nos dados internos do contrato")
            
            logger.info("Dados internos do contrato preparados")
            
            # 3. Verificar se o odontograma é de um dependente
            # Se dependente_id não foi passado como parâmetro, detectar automaticamente
            if dependente_id is None:
                with DatabaseConnection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT dependente_id 
                        FROM odontogramas 
                        WHERE id = %s
                    """, (odontograma_id,))
                    odonto_row = cursor.fetchone()
                    if odonto_row and odonto_row[0]:
                        dependente_id = odonto_row[0]
                        logger.info(f"👶 Odontograma pertence ao dependente ID (detectado automaticamente): {dependente_id}")
            else:
                logger.info(f"👶 Usando dependente_id passado como parâmetro: {dependente_id}")
            
            # 4. Buscar dados do paciente e odontograma
            logger.info("🔍 Buscando dados do contrato...")
            dados = self._get_contract_data(paciente_id, odontograma_id, contract_data, dependente_id)
            logger.info("Dados necessários do contrato carregados")
            
            # 5. Gerar token único
            logger.info("🔐 Gerando token...")
            token = self._generate_token()
            logger.info("Token de contrato gerado")
            
            # 6. Salvar no banco
            logger.info("💾 Salvando no banco...")
            
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO digital_contracts (
                        uuid, paciente_id, odontograma_id, dependente_id, valor_total,
                        access_token, expires_at, status, contract_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    str(uuid.uuid4()),
                    paciente_id,
                    odontograma_id,
                    dependente_id,
                    dados['valor_total'],
                    token,
                    datetime.now() + timedelta(hours=72),  # 3 dias
                    'draft',
                    json.dumps(contract_data) if contract_data else None
                ))
                contract_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"✅ Contrato salvo com ID: {contract_id}")
            
            # 5. Retornar link
            link = f"{PUBLIC_BASE_URL}/contrato/{token}"
            logger.info("Link do contrato preparado (contrato_id=%s)", contract_id)
            return link
            
        except Exception as e:
            logger.error("Falha ao criar contrato (%s)", type(e).__name__)
            raise
    
    def get_contract_for_client(self, token: str) -> dict:
        """
        Cliente acessa o contrato pelo token
        """
        logger.info("Consulta pública de contrato iniciada")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                logger.info("🔍 Buscando contrato no banco...")
                cursor.execute("""
                    SELECT c.id, c.paciente_id, c.valor_total, c.status, c.expires_at,
                           p.nome_paciente, p.cpf_cnpj, p.street, p.city, c.contract_data,
                           c.odontograma_id, c.dependente_id
                    FROM digital_contracts c
                    JOIN pacientes p ON c.paciente_id = p.paciente_id
                    WHERE c.access_token = %s AND c.expires_at > NOW()
                """, (token,))
                
                row = cursor.fetchone()
                if not row:
                    logger.warning("❌ Contrato não encontrado ou expirado")
                    raise Exception("Contrato não encontrado ou expirado")
                
                logger.info(f"✅ Contrato encontrado: ID={row[0]}, Status={row[3]}")
                
                # Extrair odontograma_id e dependente_id da primeira query
                odontograma_id = row[10]  # odontograma_id é o 11º campo (índice 10)
                existing_contract_data = row[9]  # contract_data é o 10º campo (índice 9)
                dependente_id = row[11]  # dependente_id é o 12º campo (índice 11)
                
                logger.info(f"📋 Odontograma ID: {odontograma_id}")
                
                # Marcar como visualizado
                cursor.execute("""
                    UPDATE digital_contracts 
                    SET status = 'opened' 
                    WHERE access_token = %s AND status = 'sent'
                """, (token,))
                conn.commit()
                
                # Buscar dados completos para o novo template
                try:
                    
                    # Extrair vendedor_nome, forma_pagamento e dia_vencimento se existir
                    vendedor_nome = None
                    forma_pagamento = None
                    dia_vencimento = None
                    if existing_contract_data:
                        if isinstance(existing_contract_data, str):
                            existing_contract_data = json.loads(existing_contract_data) if existing_contract_data else {}
                            logger.info("Dados internos existentes do contrato carregados")
                            vendedor_nome = existing_contract_data.get('vendedor_nome')
                            forma_pagamento = existing_contract_data.get('forma_pagamento')
                            dia_vencimento = existing_contract_data.get('dia_vencimento')
                            logger.info("Metadados internos do contrato extraídos")
                        elif isinstance(existing_contract_data, dict):
                            pass
                        else:
                            existing_contract_data = {}
                            logger.info(f"📋 existing_data era tipo inesperado: {type(existing_contract_data)}")
                    
                    if odontograma_id:
                        dados_completos = self._get_contract_data(row[1], odontograma_id, existing_contract_data, dependente_id)
                        logger.info("Dados completos do contrato carregados para renderização")
                        
                        # Sobrescrever com os valores extraídos do contract_data se eles existirem
                        if vendedor_nome:
                            dados_completos['vendedor_nome'] = vendedor_nome
                            logger.info("Vendedor restaurado dos dados internos do contrato")
                        if forma_pagamento:
                            dados_completos['forma_pagamento'] = forma_pagamento
                            logger.info("Forma de pagamento restaurada dos dados internos do contrato")
                        if dia_vencimento is not None:
                            dados_completos['dia_vencimento'] = dia_vencimento
                            logger.info("Dia de vencimento restaurado dos dados internos do contrato")
                        
                        logger.info("Metadados internos aplicados aos dados do contrato")
                        contract_html = self._render_contract_html(dados_completos, odontograma_id)
                    else:
                        # Fallback para template simples
                        fallback_data = {
                            'paciente_nome': row[5],
                            'paciente_cpf': row[6],
                            'endereco': f"{row[7]}, {row[8]}",
                            'valor_total': float(row[2])
                        }
                        if vendedor_nome:
                            fallback_data['vendedor_nome'] = vendedor_nome
                        contract_html = self._render_contract_html(fallback_data)
                except Exception as e:
                    logger.warning("Falha ao buscar dados completos; usando fallback (%s)", type(e).__name__)
                    # Fallback para template simples
                    fallback_data = {
                        'paciente_nome': row[5],
                        'paciente_cpf': row[6],
                        'endereco': f"{row[7]}, {row[8]}",
                        'valor_total': float(row[2])
                    }
                    contract_html = self._render_contract_html(fallback_data)
                
                result = {
                    'contract_id': row[0],
                    'paciente_nome': row[5],
                    'paciente_cpf': row[6],
                    'endereco': f"{row[7]}, {row[8]}",
                    'valor_total': float(row[2]),
                    'status': row[3],
                    'contract_html': contract_html
                }
                
                logger.info("Dados do contrato preparados para retorno (contrato_id=%s)", row[0])
                return result
                
        except Exception as e:
            logger.error("Falha ao obter contrato para o cliente (%s)", type(e).__name__)
            raise
    
    def save_selfie(self, token: str, selfie_base64: str, device_info: dict) -> dict:
        """
        Salva selfie do cliente
        """
        logger.info("Salvamento de selfie de contrato iniciado")
        
        try:
            # Calcular tamanho
            selfie_size_chars = len(selfie_base64) if selfie_base64 else 0
            selfie_size_kb = selfie_size_chars * 3 / 4 / 1024
            logger.info(f"📊 Tamanho da selfie: {selfie_size_chars} chars (~{selfie_size_kb:.2f} KB)")
            
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Verificar contrato
                logger.info("🔍 Verificando contrato...")
                cursor.execute("""
                    SELECT id, contract_data FROM digital_contracts 
                    WHERE access_token = %s AND expires_at > NOW()
                """, (token,))
                
                row = cursor.fetchone()
                if not row:
                    logger.warning("❌ Contrato não encontrado")
                    raise Exception("Contrato não encontrado")
                
                contract_id, existing_data = row
                logger.info(f"✅ Contrato encontrado: ID={contract_id}")
                
                # Preparar dados
                logger.info("📝 Preparando dados...")
                # Verificar se existing_data é string ou dict
                if isinstance(existing_data, str):
                    data = json.loads(existing_data) if existing_data else {}
                    logger.info("📋 existing_data era string JSON")
                elif isinstance(existing_data, dict):
                    data = existing_data
                    logger.info("📋 existing_data já era dict")
                else:
                    data = {}
                    logger.info(f"📋 existing_data era tipo inesperado: {type(existing_data)}")
                
                # Adicionar selfie e informações
                data.update({
                    'selfie': selfie_base64,
                    'selfie_timestamp': datetime.now().isoformat(),
                    'device_info': device_info
                })
                
                data_json = json.dumps(data)
                logger.info(f"📦 Dados JSON preparados: {len(data_json)} chars")
                
                # Salvar
                logger.info("💾 Salvando selfie no banco...")
                cursor.execute("""
                    UPDATE digital_contracts 
                    SET contract_data = %s, 
                        status = 'selfie_taken',
                        selfie_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (data_json, contract_id))
                conn.commit()
                
                logger.info("✅ Selfie salva com sucesso")
                return {'success': True, 'message': 'Selfie salva com sucesso'}
                
        except Exception as e:
            logger.error("Falha ao salvar selfie do contrato (%s)", type(e).__name__)
            raise
    
    def sign_contract(self, token: str, signature_base64: str) -> dict:
        """
        Finaliza assinatura do contrato
        """
        logger.info("Assinatura de contrato iniciada")
        
        try:
            # Validar assinatura
            if not signature_base64:
                logger.error("❌ Assinatura vazia recebida")
                raise Exception("Assinatura não pode estar vazia")
            
            # Obter informações da assinatura (já processada pelo router)
            image_info = ImageOptimizer.get_image_info(signature_base64)
            logger.info(f"📊 Assinatura recebida: {image_info['size_kb']:.2f} KB ({image_info.get('format', 'UNKNOWN')})")
            
            # Usar a assinatura já otimizada
            final_signature = signature_base64
            
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Verificar contrato e selfie
                logger.info("🔍 Verificando contrato e status...")
                cursor.execute("""
                    SELECT id, contract_data, status FROM digital_contracts 
                    WHERE access_token = %s AND expires_at > NOW()
                """, (token,))
                
                row = cursor.fetchone()
                if not row:
                    logger.warning("❌ Contrato não encontrado")
                    raise Exception("Contrato não encontrado")
                
                contract_id, existing_data, status = row
                logger.info(f"✅ Contrato encontrado: ID={contract_id}, Status={status}")
                
                if status != 'selfie_taken':
                    logger.warning(f"❌ Status inválido: {status}. Esperado: selfie_taken")
                    raise Exception("Selfie obrigatória antes da assinatura")
                
                # Preparar dados finais
                logger.info("📝 Preparando dados finais...")
                
                # Verificar se existing_data é string ou dict
                if isinstance(existing_data, str):
                    data = json.loads(existing_data) if existing_data else {}
                    logger.info("📋 existing_data era string JSON")
                elif isinstance(existing_data, dict):
                    data = existing_data
                    logger.info("📋 existing_data já era dict")
                else:
                    data = {}
                    logger.info(f"📋 existing_data era tipo inesperado: {type(existing_data)}")
                
                # Adicionar dados da assinatura otimizada
                data.update({
                    'signature': final_signature,
                    'signature_timestamp': datetime.now().isoformat(),
                    'signature_format': image_info.get('format', 'UNKNOWN'),
                    'signature_optimized': True,
                    'signature_info': {
                        'size_kb': image_info.get('size_kb', 0),
                        'dimensions': image_info.get('dimensions'),
                        'mime_type': image_info.get('mime_type', 'unknown')
                    },
                    'completed': True
                })
                
                data_json = json.dumps(data)
                data_json_size_kb = len(data_json) / 1024
                logger.info(f"📦 Dados JSON completos: {len(data_json)} chars (~{data_json_size_kb:.2f} KB)")
                
                if data_json_size_kb > 1024:  # > 1MB
                    logger.warning(f"⚠️ DADOS JSON MUITO GRANDES: {data_json_size_kb:.2f} KB!")
                
                # Finalizar contrato
                logger.info("💾 Finalizando contrato no banco...")
                cursor.execute("""
                    UPDATE digital_contracts 
                    SET contract_data = %s, 
                        status = 'signed',
                        signed_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (data_json, contract_id))
                conn.commit()
                
                logger.info("🎉 Contrato assinado com sucesso!")
                logger.info(f"📊 Resumo final:")
                logger.info(f"   🖼️ Formato: {image_info.get('format', 'UNKNOWN')}")
                logger.info(f"   🎨 Otimizada: Sim")
                logger.info(f"   📏 Tamanho final: {image_info.get('size_kb', 0):.2f} KB")
                
                return {
                    'success': True, 
                    'message': 'Contrato assinado com sucesso',
                    'signature_info': {
                        'format': image_info.get('format', 'UNKNOWN'),
                        'optimized': True,
                        'final_size_kb': image_info.get('size_kb', 0)
                    }
                }
                
        except Exception as e:
            logger.error("Falha ao assinar contrato (%s)", type(e).__name__)
            raise
    
    def is_contract_signed(self, odontograma_id: int) -> bool:
        """
        Verifica se odontograma tem contrato assinado
        """
        logger.info(f"🔍 SERVICE: is_contract_signed - odontograma_id={odontograma_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM digital_contracts 
                    WHERE odontograma_id = %s AND status = 'signed'
                """, (odontograma_id,))
                result = cursor.fetchone() is not None
                logger.info(f"✅ Resultado: {result}")
                return result
                
        except Exception as e:
            logger.error("Falha ao consultar assinatura do contrato (%s)", type(e).__name__)
            raise
    
    def check_contract_status(self, odontograma_id: int) -> dict | None:
        """
        Verifica o status do contrato para um odontograma
        """
        logger.info(f"🔍 SERVICE: check_contract_status - odontograma_id={odontograma_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                logger.info("🔍 Buscando contrato no banco...")
                
                cursor.execute("""
                    SELECT c.id, c.odontograma_id, c.access_token, c.status, 
                           c.signed_at, c.expires_at, c.created_at,
                           p.nome_paciente,
                           CASE WHEN c.expires_at > NOW() THEN 1 ELSE 0 END as is_valid
                    FROM digital_contracts c
                    LEFT JOIN pacientes p ON c.paciente_id = p.paciente_id
                    WHERE c.odontograma_id = %s
                    ORDER BY 
                        CASE WHEN c.status = 'signed' THEN 0 ELSE 1 END,
                        c.created_at DESC
                    LIMIT 1
                """, (odontograma_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.info(f"📭 Nenhum contrato encontrado para odontograma {odontograma_id}")
                    return None
                
                is_valid = bool(row[8])  # is_valid vem como 0 ou 1 do banco
                logger.info(f"✅ Contrato encontrado: ID={row[0]}, Status={row[3]}, Válido={is_valid}")
                
                # Se o contrato não está assinado E está expirado, retornar None
                if row[3] != 'signed' and not is_valid:
                    logger.warning(f"⚠️ Contrato ID={row[0]} está expirado e não assinado. Ignorando.")
                    return None
                
                # Montar URL do contrato se tiver token E estiver válido (ou assinado)
                contract_url = ""
                if row[2] and (is_valid or row[3] == 'signed'):  # access_token e (válido ou assinado)
                    contract_url = f"{PUBLIC_BASE_URL}/contrato/{row[2]}"
                
                result = {
                    'id': row[0],
                    'odontograma_id': row[1],
                    'contract_url': contract_url,
                    'is_signed': row[3] == 'signed',
                    'signed_at': row[4].isoformat() if row[4] else None,
                    'patient_name': row[7],
                    'signature_ip': None,  # Não temos esse campo ainda
                    'created_at': row[6].isoformat() if row[6] else None,
                    'expires_at': row[5].isoformat() if row[5] else None,
                    'is_valid': is_valid
                }
                
                logger.info(f"✅ Status do contrato preparado: is_signed={result['is_signed']}")
                return result
                
        except Exception as e:
            logger.error("Falha ao consultar status do contrato (%s)", type(e).__name__)
            raise
    
    def _generate_token(self) -> str:
        """Gera token único"""
        token = hashlib.sha256(f"{uuid.uuid4()}{datetime.now()}".encode()).hexdigest()[:32]
        logger.info("Token de contrato gerado")
        return token
    
    def _get_contract_data(self, paciente_id: int, odontograma_id: int, contract_data_json: dict = None, dependente_id: int = None) -> dict:
        """Busca dados completos para o contrato"""
        logger.info(f"📋 Buscando dados do contrato - paciente_id={paciente_id}, odontograma_id={odontograma_id}, dependente_id={dependente_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar dados do paciente, odontograma e valor total
                cursor.execute("""
                    SELECT 
                        p.nome_paciente, 
                        p.cpf_cnpj,
                        p.rg_ie,
                        p.data_nascimento,
                        p.email,
                        p.street,
                        p.street_number,
                        p.neighborhood,
                        p.city,
                        p.state,
                        p.zip_code,
                        p.phone_area_code,
                        p.phone_number,
                        o.id,
                        COALESCE(SUM(oi.valor_registrado), 0) as valor_total,
                        o.tipo as tipo_nome,
                        t.valor_base as tipo_valor_base,
                        t.qtd_parcelas as tipo_qtd_parcelas
                    FROM pacientes p
                    JOIN odontogramas o ON p.paciente_id = o.paciente_id
                    LEFT JOIN odontograma_itens oi ON o.id = oi.odontograma_id
                    LEFT JOIN tipos_odontograma t ON LOWER(o.tipo) = LOWER(t.nome)
                    WHERE p.paciente_id = %s AND o.id = %s
                    GROUP BY p.paciente_id, p.nome_paciente, p.cpf_cnpj, p.rg_ie, 
                             p.data_nascimento, p.email, p.street, p.street_number, 
                             p.neighborhood, p.city, p.state, p.zip_code, 
                             p.phone_area_code, p.phone_number, o.id, o.tipo, 
                             t.valor_base, t.qtd_parcelas
                """, (paciente_id, odontograma_id))
                
                row = cursor.fetchone()
                if not row:
                    logger.error(f"❌ Nenhum dado encontrado para paciente_id={paciente_id}, odontograma_id={odontograma_id}")
                    raise Exception(f"Dados não encontrados para paciente {paciente_id} e odontograma {odontograma_id}")
                
                # Formatar telefone
                telefone = ""
                if row[11] and row[12]:  # phone_area_code e phone_number
                    telefone = f"({row[11]}){row[12]}"
                elif row[12]:
                    telefone = row[12]
                
                # Formatar endereço completo
                endereco_completo = ""
                endereco_parts = []
                if row[5]:  # street
                    endereco_parts.append(row[5])
                if row[6]:  # street_number
                    endereco_parts.append(row[6])
                if endereco_parts:
                    endereco_completo = ", ".join(endereco_parts)
                
                # Determinar valor total e quantidade de parcelas
                valor_items = float(row[14]) if row[14] else 0.0
                tipo_nome = row[15]
                tipo_valor_base = float(row[16]) if row[16] else None
                tipo_qtd_parcelas = row[17] if row[17] else None
                
                # Inicializar result para poder adicionar campos de entrada/taxa
                result = {}
                
                # Para PARTICULAR e ORTODONTIA, verificar se há qtd_parcelas no contract_data ou na venda
                if tipo_nome in ['Particular', 'Ortodontia']:
                    # Primeiro, verificar se foi passado via contract_data_json
                    if contract_data_json and contract_data_json.get('qtd_parcelas') is not None:
                        qtd_parcelas = contract_data_json.get('qtd_parcelas')
                        valor_total = valor_items  # Usar o valor dos itens
                        valor_mensalidade = valor_total / qtd_parcelas if qtd_parcelas > 0 else valor_total
                        logger.info("Quantidade de parcelas restaurada dos dados internos")
                    else:
                        # Se não, verificar na venda
                        logger.info("Quantidade de parcelas consultada na venda")
                        cursor.execute("""
                            SELECT qtd_parcelas, valor_entrada, valor_taxa_adesao, 
                                   tipo_cobranca_inicial, entrada_automatica, 
                                   percentual_desconto_avista
                            FROM vendas
                            WHERE odontograma_id = %s
                            ORDER BY id DESC
                            LIMIT 1
                        """, (odontograma_id,))
                        
                        venda_row = cursor.fetchone()
                        if venda_row and venda_row[0]:
                            qtd_parcelas = venda_row[0]
                            valor_total = valor_items  # Usar o valor dos itens
                            valor_mensalidade = valor_total / qtd_parcelas if qtd_parcelas > 0 else valor_total
                            logger.info("Quantidade de parcelas localizada na venda")
                            
                            # Adicionar dados de entrada/taxa da venda
                            if venda_row[1]:  # valor_entrada
                                result['valor_entrada'] = float(venda_row[1])
                                logger.info("Entrada financeira localizada para o contrato")
                            if venda_row[2]:  # valor_taxa_adesao
                                result['valor_taxa_adesao'] = float(venda_row[2])
                                logger.info("Taxa de adesão localizada para o contrato")
                            if venda_row[3]:  # tipo_cobranca_inicial
                                result['tipo_cobranca_inicial'] = venda_row[3]
                                logger.info("Tipo de cobrança inicial localizado")
                            if venda_row[4] is not None:  # entrada_automatica
                                result['entrada_automatica'] = venda_row[4]
                                logger.info("Configuração de entrada automática localizada")
                            if venda_row[5]:  # percentual_desconto_avista
                                result['percentual_desconto_avista'] = float(venda_row[5])
                                logger.info("Desconto à vista localizado para o contrato")
                        else:
                            # Fallback para valores padrão do tipo
                            valor_total = valor_items
                            qtd_parcelas = tipo_qtd_parcelas if tipo_qtd_parcelas else 12
                            valor_mensalidade = valor_total / qtd_parcelas if qtd_parcelas > 0 else valor_total
                            logger.info("Venda não encontrada; quantidade padrão de parcelas aplicada")
                
                # Se o tipo tem valor_base definido, usar ele como mensalidade
                elif tipo_valor_base and tipo_valor_base > 0:
                    # O valor_base é a mensalidade/parcela
                    valor_mensalidade = tipo_valor_base
                    qtd_parcelas = tipo_qtd_parcelas if tipo_qtd_parcelas else 12
                    # Calcular o valor total multiplicando mensalidade x parcelas
                    valor_total = valor_mensalidade * qtd_parcelas
                    logger.info("Valor base do tipo de contrato calculado")
                    
                    # Buscar dados de entrada/taxa para contratos com valor base
                    logger.info("Entrada e taxa consultadas para o tipo de contrato")
                    cursor.execute("""
                        SELECT valor_entrada, valor_taxa_adesao, tipo_cobranca_inicial, 
                               entrada_automatica, percentual_desconto_avista
                        FROM vendas
                        WHERE odontograma_id = %s
                        ORDER BY id DESC
                        LIMIT 1
                    """, (odontograma_id,))
                    
                    venda_row = cursor.fetchone()
                    if venda_row:
                        if venda_row[0]:  # valor_entrada
                            result['valor_entrada'] = float(venda_row[0])
                            logger.info("Entrada financeira localizada para o contrato")
                        if venda_row[1]:  # valor_taxa_adesao
                            result['valor_taxa_adesao'] = float(venda_row[1])
                            logger.info("Taxa de adesão localizada para o contrato")
                        if venda_row[2]:  # tipo_cobranca_inicial
                            result['tipo_cobranca_inicial'] = venda_row[2]
                            logger.info("Tipo de cobrança inicial localizado")
                        if venda_row[3] is not None:  # entrada_automatica
                            result['entrada_automatica'] = venda_row[3]
                            logger.info("Configuração de entrada automática localizada")
                        if venda_row[4]:  # percentual_desconto_avista
                            result['percentual_desconto_avista'] = float(venda_row[4])
                            logger.info("Desconto à vista localizado para o contrato")
                else:
                    # Para tipos sem valor_base, usar soma dos itens
                    valor_total = valor_items
                    qtd_parcelas = tipo_qtd_parcelas if tipo_qtd_parcelas else 12
                    valor_mensalidade = None
                    logger.info("Valor do contrato calculado pela soma dos itens")
                
                # Atualizar result com todos os dados básicos
                result.update({
                    'paciente_nome': row[0] or '',
                    'paciente_cpf': row[1] or '',
                    'paciente_rg': row[2] or '',
                    'paciente_data_nascimento': row[3].strftime("%d/%m/%Y") if row[3] else '',
                    'paciente_email': row[4] or '',
                    'paciente_endereco': endereco_completo,
                    'paciente_bairro': row[7] or '',
                    'paciente_cidade': row[8] or '',
                    'paciente_estado': row[9] or '',
                    'paciente_cep': row[10] or '',
                    'paciente_telefone1': telefone,
                    'paciente_telefone2': '',  # Segundo telefone não disponível
                    'endereco_completo': f"{endereco_completo}, {row[7] or ''}, {row[8] or ''}",
                    'valor_total': valor_total,
                    'qtd_parcelas': qtd_parcelas,
                    'valor_mensalidade': valor_mensalidade,
                    'valor_base_contrato': valor_mensalidade,  # Para compatibilidade com template
                    'dia_vencimento': '10',  # Padrão inicial
                    'forma_pagamento': 'A DEFINIR',  # Padrão caso não seja especificado
                    'observacao_tratamentos': 'CONFORME ORÇAMENTO APRESENTADO'
                })

                # Se contract_data_json for fornecido e contiver dia_vencimento, usá-lo
                if contract_data_json and contract_data_json.get('dia_vencimento') is not None:
                    result['dia_vencimento'] = contract_data_json.get('dia_vencimento')
                    logger.info("Dia de vencimento atualizado a partir dos dados internos")
                
                # Log para forma de pagamento e dia de vencimento antes de retornar
                logger.info("Dados financeiros do contrato preparados")

                if contract_data_json:
                    forma_pagamento_extraida = contract_data_json.get('forma_pagamento')
                    if forma_pagamento_extraida:
                        result['forma_pagamento'] = forma_pagamento_extraida
                        logger.info("Forma de pagamento restaurada dos dados internos")

                    dia_vencimento_extraido = contract_data_json.get('dia_vencimento')
                    if dia_vencimento_extraido is not None:
                        result['dia_vencimento'] = dia_vencimento_extraido
                        logger.info("Dia de vencimento restaurado dos dados internos")
                    else:
                        logger.info("Dia de vencimento ausente nos dados internos; valor existente preservado")
                    
                    # Adicionar processamento do vendedor_nome
                    vendedor_nome_extraido = contract_data_json.get('vendedor_nome')
                    if vendedor_nome_extraido:
                        result['vendedor_nome'] = vendedor_nome_extraido
                        logger.info("Vendedor restaurado dos dados internos")
                    else:
                        logger.info("Vendedor ausente nos dados internos")

                    # Adicionar processamento de qtd_parcelas
                    qtd_parcelas_extraido = contract_data_json.get('qtd_parcelas')
                    if qtd_parcelas_extraido is not None:
                        result['qtd_parcelas'] = qtd_parcelas_extraido
                        # Recalcular valor da parcela com a qtd_parcelas atualizada
                        result['valor_parcela'] = result['valor_total'] / qtd_parcelas_extraido if qtd_parcelas_extraido > 0 else result['valor_total']
                        result['valor_mensalidade'] = result['valor_parcela']
                        result['valor_base_contrato'] = result['valor_parcela']
                        logger.info("Quantidade de parcelas restaurada dos dados internos")

                logger.info("Dados internos processados para o contrato")
                
                # Buscar produtos do odontograma (ainda dentro do mesmo with DatabaseConnection())
                cursor.execute("""
                    SELECT 
                        p.nome as produto_nome,
                        oi.valor_registrado,
                        oi.dente_numero,
                        oi.face_vestibular,
                        oi.face_lingual_palatina,
                        oi.face_mesial,
                        oi.face_distal,
                        oi.face_oclusal_incisal
                    FROM odontograma_itens oi
                    JOIN produtos p ON oi.produto_id = p.id
                    WHERE oi.odontograma_id = %s
                    ORDER BY oi.created_at
                """, (odontograma_id,))
                
                produtos_rows = cursor.fetchall()
                produtos_list = []
                
                for produto_row in produtos_rows:
                    # Montar faces ativas
                    faces = []
                    if produto_row[3]:  # face_vestibular
                        faces.append('Vestibular')
                    if produto_row[4]:  # face_lingual_palatina
                        faces.append('Lingual/Palatina')
                    if produto_row[5]:  # face_mesial
                        faces.append('Mesial')
                    if produto_row[6]:  # face_distal
                        faces.append('Distal')
                    if produto_row[7]:  # face_oclusal_incisal
                        faces.append('Oclusal/Incisal')
                    
                    face_str = ', '.join(faces) if faces else ''
                    
                    produto_info = {
                        'nome': produto_row[0],
                        'valor': float(produto_row[1]) if produto_row[1] else 0.0,
                        'quantidade': 1,  # Sempre 1 por padrão
                        'face': face_str,
                        'dente': produto_row[2] or '',
                        'descricao': ''  # Não temos descrição na tabela produtos
                    }
                    produtos_list.append(produto_info)
                
                result['produtos_odontograma'] = produtos_list
                logger.info(f"✅ {len(produtos_list)} produtos encontrados no odontograma")
                
                # Se o contrato for para um dependente, buscar dados do dependente
                if dependente_id:
                    logger.info(f"👶 Buscando dados do dependente ID: {dependente_id}")
                    cursor.execute("""
                        SELECT 
                            d.nome_dependente,
                            d.data_nascimento_dependente,
                            d.parentesco,
                            d.observacoes_dependente
                        FROM dependentes d
                        WHERE d.dependente_id = %s
                    """, (dependente_id,))
                    
                    dep_row = cursor.fetchone()
                    if dep_row:
                        result['is_dependente_contract'] = True
                        result['dependente_id'] = dependente_id
                        result['dependente_nome'] = dep_row[0] or ''
                        result['dependente_cpf'] = ''  # Dependentes não têm CPF cadastrado
                        result['dependente_data_nascimento'] = dep_row[1].strftime("%d/%m/%Y") if dep_row[1] else ''
                        result['dependente_parentesco'] = dep_row[2] or ''
                        result['dependente_rg'] = ''  # Dependentes não têm RG cadastrado
                        result['observacoes_dependente'] = dep_row[3] or ''
                        
                        # Adicionar info do responsável (já temos os dados do paciente titular)
                        result['responsavel_nome'] = result['paciente_nome']
                        result['responsavel_cpf'] = result['paciente_cpf']
                        
                        logger.info("Dados do dependente localizados (dependente_id=%s)", dependente_id)
                    else:
                        logger.warning(f"⚠️ Dependente ID {dependente_id} não encontrado")
                        result['is_dependente_contract'] = False
                else:
                    result['is_dependente_contract'] = False
                
                return result
                
        except Exception as e:
            logger.error("Falha ao carregar dados do contrato (%s)", type(e).__name__)
            raise
    
    def _render_contract_html(self, dados: dict, odontograma_id: int = None) -> str:
        """Renderiza HTML do contrato"""
        logger.info("Renderização do HTML do contrato iniciada")
        
        try:
            # Usar o template manager se tiver odontograma_id
            if odontograma_id:
                html = template_manager.render_contract_with_template(odontograma_id, dados)
            else:
                # Fallback para o template padrão
                from .templates import render_contract
                html = render_contract(dados)
            
            logger.info(f"✅ HTML renderizado: {len(html)} caracteres")
            return html
            
        except Exception as e:
            logger.error("Falha ao renderizar HTML do contrato (%s)", type(e).__name__)
            raise
    
    def get_signed_contract_data(self, odontograma_id: int) -> dict | None:
        """
        Retorna dados completos do contrato assinado incluindo selfie e assinatura
        """
        logger.info(f"🔍 SERVICE: get_signed_contract_data - odontograma_id={odontograma_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                logger.info("🔍 Buscando contrato assinado no banco...")
                
                cursor.execute("""
                    SELECT c.id, c.paciente_id, c.valor_total, c.status, c.contract_data,
                           c.signed_at, c.selfie_at, c.expires_at,
                           p.nome_paciente, p.cpf_cnpj, p.street, p.city, p.state, p.phone_number
                    FROM digital_contracts c
                    JOIN pacientes p ON c.paciente_id = p.paciente_id
                    WHERE c.odontograma_id = %s AND c.status = 'signed'
                    ORDER BY c.signed_at DESC
                    LIMIT 1
                """, (odontograma_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"❌ Nenhum contrato assinado encontrado para odontograma {odontograma_id}")
                    return None
                
                logger.info(f"✅ Contrato assinado encontrado: ID={row[0]}")
                
                # Processar contract_data (JSONB)
                contract_data = row[4]
                if isinstance(contract_data, str):
                    contract_data = json.loads(contract_data) if contract_data else {}
                elif not isinstance(contract_data, dict):
                    contract_data = {}
                
                # Buscar dados completos para o HTML
                # Primeiro verificar se tem dependente_id no contrato
                cursor.execute("""
                    SELECT dependente_id
                    FROM digital_contracts
                    WHERE id = %s
                """, (row[0],))
                dep_result = cursor.fetchone()
                dependente_id = dep_result[0] if dep_result and dep_result[0] else None
                
                # Recalcular valor total considerando descontos aplicados
                valor_total_recalculado = self._recalcular_valor_com_desconto(odontograma_id, float(row[2]))
                
                dados_completos = self._get_contract_data(row[1], odontograma_id, contract_data, dependente_id)
                
                # Atualizar o valor_total com desconto se aplicável
                dados_completos['valor_total'] = valor_total_recalculado
                dados_completos['valor_parcela'] = valor_total_recalculado / dados_completos.get('qtd_parcelas', 1)
                dados_completos['valor_mensalidade'] = dados_completos['valor_parcela']
                dados_completos['valor_base_contrato'] = dados_completos['valor_parcela']
                
                # IMPORTANTE: Sobrescrever com dados do contract_data se existirem
                # Isso garante que vendedor_nome e forma_pagamento sejam preservados
                if contract_data.get('vendedor_nome'):
                    dados_completos['vendedor_nome'] = contract_data.get('vendedor_nome')
                    logger.info("Vendedor recuperado dos dados internos")
                else:
                    logger.warning(f"⚠️ Vendedor NÃO encontrado no contract_data armazenado")
                    
                if contract_data.get('forma_pagamento'):
                    dados_completos['forma_pagamento'] = contract_data.get('forma_pagamento')
                    logger.info("Forma de pagamento recuperada dos dados internos")
                
                if contract_data.get('dia_vencimento') is not None:
                    dados_completos['dia_vencimento'] = contract_data.get('dia_vencimento')
                    logger.info("Dia de vencimento recuperado dos dados internos")
                
                # Adicionar a assinatura aos dados completos para renderização
                if contract_data.get('signature'):
                    dados_completos['assinatura_base64'] = contract_data.get('signature')
                
                result = {
                    'contract_id': row[0],
                    'paciente_id': row[1],
                    'paciente_nome': row[8],
                    'paciente_cpf': row[9],
                    'endereco': f"{row[10]}, {row[11]}, {row[12]}",
                    'telefone': row[13],
                    'valor_total': valor_total_recalculado,
                    'status': row[3],
                    'signed_at': row[5].isoformat() if row[5] else None,
                    'selfie_at': row[6].isoformat() if row[6] else None,
                    'selfie': contract_data.get('selfie'),
                    'signature': contract_data.get('signature'),
                    'contract_html': self._render_contract_html(dados_completos, odontograma_id)
                }
                
                logger.info(f"✅ Dados do contrato assinado preparados com sucesso")
                return result
                
        except Exception as e:
            logger.error("Falha ao obter dados do contrato assinado (%s)", type(e).__name__)
            raise
    
    def _recalcular_valor_com_desconto(self, odontograma_id: int, valor_original: float) -> float:
        """
        Recalcula o valor total considerando descontos aprovados para o odontograma
        """
        try:
            logger.info("Recálculo de desconto iniciado (odontograma_id=%s)", odontograma_id)
            
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar desconto aprovado para este odontograma
                cursor.execute("""
                    SELECT valor_solicitado, percentual_solicitado, status_aprovacao
                    FROM solicitacoes_desconto 
                    WHERE odontograma_id = %s 
                    AND status_aprovacao = 'Aprovado'
                    ORDER BY data_aprovacao DESC 
                    LIMIT 1
                """, (odontograma_id,))
                
                desconto_row = cursor.fetchone()
                if desconto_row:
                    valor_desconto, percentual_desconto, status = desconto_row
                    valor_final = valor_original - float(valor_desconto)
                    logger.info("Desconto aprovado aplicado ao contrato")
                    return valor_final
                else:
                    logger.info("Nenhum desconto aprovado encontrado; valor original preservado")
                    return valor_original
                    
        except Exception as e:
            logger.error("Falha ao recalcular desconto (%s)", type(e).__name__)
            # Em caso de erro, retornar valor original
            return valor_original
