import logging
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from ..database.db import DatabaseConnection
from ..carne_sdk.split_manager import SplitManager

logger = logging.getLogger(__name__)

# Mapeamento de receiver_ids específicos por unidade
RECEIVER_ID_ESPECIFICO_POR_UNIDADE = {
    # AKI MAIS (ID 2)
    (2, 'São João de Meriti'): '21',
    (2, 'Vilar dos Teles'): '17',

    # J & F 2021 (ID 3)
    (3, 'São João de Meriti'): '20',
    (3, 'Vilar dos Teles'): '16',
}

# Constantes para IDs dos cargos
class CargoIDs:
    ADMINISTRADOR = 1
    AVALIADOR = 2
    COMERCIAL = 3
    GERENTE = 4
    DENTISTA = 5
    FINANCEIRO = 6
    RECEPCAO = 7
    STREET = 8
    SUPERVISOR = 9
    CRC = 10

# Mapeamento de regras condicionais
# cargo_vendedor -> cargo_beneficiado (pode ser lista para múltiplos beneficiados)
# IMPORTANTE: Gerente e Supervisor quando vendem, apenas eles entram como cargo (sem beneficiados)
REGRAS_SPLIT_CONDICIONAL = {
    CargoIDs.COMERCIAL: [CargoIDs.GERENTE],
    CargoIDs.CRC: [CargoIDs.SUPERVISOR, CargoIDs.GERENTE]
}

# Cargos autorizados a realizar vendas
CARGOS_AUTORIZADOS_VENDA = [
    CargoIDs.COMERCIAL,
    CargoIDs.GERENTE,
    CargoIDs.SUPERVISOR,
    CargoIDs.CRC
]

class SplitService:
    """
    Serviço para gerenciar as regras de split de forma dinâmica,
    baseado nas configurações do banco de dados.
    """

    SPLIT_API_FIELDS = ("sellerId", "percentage", "cyclesToParticipate", "absorbBalance", "absorbFee")

    @staticmethod
    def sanitizar_splits_para_api(splits: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Remove metadados internos antes de enviar splits para a API de pagamento."""
        if not splits:
            return []

        splits_api = []
        for split in splits:
            split_api = {
                "sellerId": split.get("sellerId", split.get("seller_id")),
                "percentage": split.get("percentage"),
                "cyclesToParticipate": split.get("cyclesToParticipate", split.get("cycles_to_participate")),
                "absorbBalance": split.get("absorbBalance", split.get("absorb_balance", False)),
            }

            if "absorbFee" in split:
                split_api["absorbFee"] = split["absorbFee"]

            splits_api.append({
                key: value
                for key, value in split_api.items()
                if value is not None
            })
        return splits_api

    @staticmethod
    def get_receiver_id_especifico(empresa_id: int, unidade_venda: str, receiver_id_original: str) -> str:
        """
        Retorna receiver_id específico baseado na empresa e unidade da venda.
        Se não houver mapeamento específico, retorna o receiver_id original.

        Args:
            empresa_id: ID da empresa
            unidade_venda: Unidade onde a venda foi realizada
            receiver_id_original: Receiver_id original da empresa

        Returns:
            Receiver_id específico para a unidade ou o original se não houver mapeamento
        """
        receiver_id_especifico = RECEIVER_ID_ESPECIFICO_POR_UNIDADE.get((empresa_id, unidade_venda))

        if receiver_id_especifico:
            logger.info(f"Receiver ID específico encontrado: Empresa {empresa_id}, Unidade '{unidade_venda}' → {receiver_id_especifico} (era {receiver_id_original})")
            return receiver_id_especifico
        else:
            logger.debug(f"Nenhum receiver_id específico para Empresa {empresa_id}, Unidade '{unidade_venda}'. Usando original: {receiver_id_original}")
            return receiver_id_original
    
    @staticmethod
    def validar_cargo_autorizado_venda(usuario_id: int) -> Tuple[bool, Optional[str]]:
        """
        Valida se um usuário tem cargo autorizado para realizar vendas.
        
        Args:
            usuario_id: ID do usuário
            
        Returns:
            Tupla (autorizado, mensagem_erro)
        """
        logger.info(f"Validando autorização de venda para usuário ID={usuario_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar cargo do usuário
                cursor.execute("""
                    SELECT u.cargo_id, c.nome, u.nome
                    FROM users u
                    LEFT JOIN cargos c ON u.cargo_id = c.id
                    WHERE u.id = %s
                """, (usuario_id,))
                
                resultado = cursor.fetchone()
                
                if not resultado:
                    return False, "Usuário não encontrado"
                
                cargo_id, cargo_nome, usuario_nome = resultado
                
                if not cargo_id:
                    return False, f"Usuário {usuario_nome} não possui cargo definido"
                
                # Verificar se o cargo está autorizado
                if cargo_id in CARGOS_AUTORIZADOS_VENDA:
                    logger.info(f"Venda autorizada para {usuario_nome} - Cargo: {cargo_nome}")
                    return True, None
                else:
                    mensagem = f"Cargo '{cargo_nome}' não está autorizado a realizar vendas. Apenas Comercial, CRC, Supervisor e Gerente podem fazer vendas."
                    logger.warning(f"Venda bloqueada para {usuario_nome} - {mensagem}")
                    return False, mensagem
                    
        except Exception as e:
            logger.error(f"Erro ao validar autorização de venda: {str(e)}")
            return False, "Erro ao validar autorização"
    
    @staticmethod
    def obter_splits_para_tipo_odontograma(tipo_odontograma_id: int, unidade: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Obtém os splits configurados para um determinado tipo de odontograma,
        respeitando os limites e prioridades definidos.
        
        Args:
            tipo_odontograma_id: ID do tipo de odontograma
            unidade: Unidade específica para buscar regras
            
        Returns:
            Lista de splits configurados pronta para uso na API ou None se não encontrar
        """
        logger.info(f"Obtendo configurações de split para tipo_odontograma_id={tipo_odontograma_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # 1. Buscar limites de configuração
                cursor.execute("""
                    SELECT max_empresas, max_cargos
                    FROM config_limite_split
                    WHERE tipo_odontograma_id = %s
                """, (tipo_odontograma_id,))
                limite_row = cursor.fetchone()
                
                # Se não houver configuração de limite, usar valores padrão
                if limite_row:
                    max_empresas, max_cargos = limite_row
                else:
                    max_empresas, max_cargos = 1, 3
                    logger.warning(f"Configuração de limite não encontrada para tipo_odontograma_id={tipo_odontograma_id}. Usando valores padrão.")
                
                # 2. Buscar empresas participantes (ativas e ordenadas por prioridade)
                cursor.execute("""
                    SELECT pe.empresa_id, ers.percentual
                    FROM participacao_empresa_split pe
                    JOIN empresa_regras_split ers ON pe.empresa_id = ers.empresa_id AND pe.tipo_odontograma_id = ers.tipo_odontograma_id
                    WHERE pe.tipo_odontograma_id = %s 
                      AND pe.ativo = TRUE
                    ORDER BY pe.ordem_prioridade
                    LIMIT %s
                """, (tipo_odontograma_id, max_empresas))
                empresas_rows = cursor.fetchall()
                
                # 3. Buscar cargos participantes (ativos e ordenados por prioridade)
                cursor.execute("""
                    SELECT pc.cargo_id, rs.percentual, c.nome as cargo_nome,
                           pc.ordem_prioridade, rs.ciclos_participacao, rs.absorve_saldo
                    FROM participacao_cargo_split pc
                    JOIN regras_split rs ON pc.cargo_id = rs.cargo_id AND pc.tipo_odontograma_id = rs.tipo_odontograma_id
                    JOIN cargos c ON pc.cargo_id = c.id
                    WHERE pc.tipo_odontograma_id = %s 
                      AND pc.ativo = TRUE
                      AND rs.ativo = TRUE
                    ORDER BY pc.ordem_prioridade
                    LIMIT %s
                """, (tipo_odontograma_id, max_cargos))
                cargos_rows = cursor.fetchall()
                
                # Se não houver participantes, retorna None
                if not empresas_rows and not cargos_rows:
                    logger.warning(f"Nenhuma configuração de split encontrada para tipo_odontograma_id={tipo_odontograma_id}")
                    return None
                
                # 4. Configurar SplitManager
                split_manager = SplitManager()
                
                # Adicionar empresas
                for empresa_id, percentual in empresas_rows:
                    # Buscar receiver_id da empresa
                    cursor.execute("""
                        SELECT bempaggo_receiver_id
                        FROM empresas
                        WHERE id = %s AND bempaggo_integration_status = 'integrado_por_cnpj'
                    """, (empresa_id,))
                    empresa_row = cursor.fetchone()
                    
                    if not empresa_row or not empresa_row[0]:
                        logger.warning(f"Empresa ID={empresa_id} não tem bempaggo_receiver_id configurado ou não está integrada")
                        continue
                    
                    receiver_id = empresa_row[0]
                    split_manager.add_split(
                        seller_id=receiver_id,
                        percentage=float(percentual),
                        cycles_to_participate=1,  # Valor padrão
                        absorb_balance=False  # Valor padrão
                    )
                
                # Adicionar cargos (apenas se houver algum)
                if cargos_rows:
                    # Criar lookup de percentuais por cargo
                    cargo_percentuais = {}
                    cargo_ciclos = {}
                    cargo_absorve = {}
                    
                    for cargo_id, percentual, cargo_nome, _, ciclos, absorve in cargos_rows:
                        cargo_percentuais[cargo_id] = percentual
                        cargo_ciclos[cargo_id] = ciclos
                        cargo_absorve[cargo_id] = absorve
                    
                    # Buscar todos os usuários relacionados aos cargos selecionados com receiver_id configurado
                    cargo_ids = tuple([row[0] for row in cargos_rows])
                    if len(cargo_ids) == 1:
                        # PostgreSQL requer tratamento especial para tuplas de um elemento
                        cargo_ids_query = f"({cargo_ids[0]})"
                    else:
                        cargo_ids_query = str(cargo_ids)
                    
                    cursor.execute(f"""
                        SELECT id, cargo_id, bempaggo_receiver_id
                        FROM users
                        WHERE cargo_id IN {cargo_ids_query}
                        AND bempaggo_integration_status IN ('integrado_por_cnpj', 'integrado_por_cpf')
                        AND bempaggo_receiver_id IS NOT NULL
                    """)
                    users_rows = cursor.fetchall()
                    
                    for user_id, cargo_id, receiver_id in users_rows:
                        if not cargo_id in cargo_percentuais:
                            continue
                        
                        split_manager.add_split(
                            seller_id=receiver_id,
                            percentage=float(cargo_percentuais[cargo_id]),
                            cycles_to_participate=cargo_ciclos.get(cargo_id, 1),
                            absorb_balance=cargo_absorve.get(cargo_id, False)
                        )
                
                # Validar se os percentuais somam 100%
                if not split_manager.validate_total_percentage():
                    logger.warning(f"Os percentuais configurados para o tipo_odontograma_id={tipo_odontograma_id} não somam 100%")
                    return None
                
                return split_manager.get_splits()
                
        except Exception as e:
            logger.error(f"Erro ao obter configurações de split: {str(e)}", exc_info=True)
            return None
            
    @staticmethod
    def obter_dentista_por_odontograma(odontograma_id: int) -> Optional[int]:
        """
        Obtém o ID do dentista orcamentista que criou o odontograma.
        
        Args:
            odontograma_id: ID do odontograma
            
        Returns:
            ID do dentista ou None se não encontrar
        """
        logger.info(f"Obtendo dentista para odontograma_id={odontograma_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT dentista_orcamentista_id
                    FROM odontogramas
                    WHERE id = %s
                """, (odontograma_id,))
                
                row = cursor.fetchone()
                if row:
                    dentista_id = row[0]
                    logger.info(f"Dentista ID={dentista_id} encontrado para odontograma_id={odontograma_id}")
                    return dentista_id
                    
                logger.warning(f"Odontograma ID={odontograma_id} não encontrado")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao buscar dentista do odontograma: {str(e)}", exc_info=True)
            return None
            
    @staticmethod
    def obter_cargo_usuario(usuario_id: int) -> Optional[int]:
        logging.debug(f"obter_cargo_usuario recebeu: tipo={type(usuario_id)}, valor={usuario_id}")
        """
        Obtém o cargo do usuário.
        
        Args:
            usuario_id: ID do usuário
            
        Returns:
            ID do cargo ou None se não encontrar
        """
        if isinstance(usuario_id, str) and not usuario_id.isdigit():
            logging.warning(f"usuario_id não é numérico: {usuario_id}. Tentando buscar por nome.")
        logger.debug(f"Obtendo cargo para usuario_id={usuario_id}")

        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cargo_id
                    FROM users
                    WHERE id = %s
                """, (usuario_id,))
                
                row = cursor.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Erro ao buscar cargo do usuário: {str(e)}", exc_info=True)
            return None
            
    @staticmethod
    def obter_user_id_dentista(dentista_id: int) -> Optional[int]:
        """
        Obtém o user_id associado ao dentista.
        
        Args:
            dentista_id: ID do dentista
            
        Returns:
            ID do usuário ou None se não encontrar
        """
        logger.debug(f"Obtendo user_id para dentista_id={dentista_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT user_id
                    FROM dentistas
                    WHERE id = %s AND user_id IS NOT NULL
                """, (dentista_id,))
                
                row = cursor.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Erro ao buscar user_id do dentista: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def obter_cargo_dentista(dentista_id: int) -> Optional[int]:
        """
        Obtém o cargo associado ao dentista, caso exista.
        
        Args:
            dentista_id: ID do dentista
            
        Returns:
            ID do cargo ou None se não encontrar
        """
        logger.debug(f"Obtendo cargo para dentista_id={dentista_id}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar pelo vínculo direto usando user_id
                cursor.execute("""
                    SELECT u.cargo_id
                    FROM users u
                    JOIN dentistas d ON d.user_id = u.id
                    WHERE d.id = %s AND u.cargo_id IS NOT NULL
                """, (dentista_id,))
                
                row = cursor.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Erro ao buscar cargo do dentista: {str(e)}", exc_info=True)
            return None
            
    @staticmethod
    def obter_splits_para_venda(
        tipo_odontograma_id: int, 
        dentista_id: Optional[int] = None, 
        usuario_id: Optional[int] = None,
        valor_total_venda: Optional[Decimal] = None,
        unidade: Optional[str] = None,
        incluir_metadata: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Determina splits com base no tipo de odontograma, dentista, usuário e valor da venda.
        Para cargos com valor fixo, calcula o percentual dinamicamente.
        Prioriza regras específicas da unidade sobre regras gerais.
        
        Args:
            tipo_odontograma_id: ID do tipo de odontograma
            dentista_id: ID do dentista orcamentista
            usuario_id: ID do usuário realizando a venda
            valor_total_venda: Valor total da venda em reais (para calcular percentual de valores fixos)
            unidade: Unidade específica para buscar regras
            
        Returns:
            Lista de splits configurados pronta para uso na API ou None se não encontrar
        """
        logger.info(f"Obtendo splits para venda: tipo={tipo_odontograma_id}, dentista={dentista_id}, usuario={usuario_id}, valor={valor_total_venda}, unidade={unidade}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # 1. Obter limites do tipo de odontograma
                cursor.execute("""
                    SELECT max_cargos, max_empresas
                    FROM config_limite_split
                    WHERE tipo_odontograma_id = %s
                """, (tipo_odontograma_id,))
                limite_row = cursor.fetchone()
                
                max_cargos = 3  # Valor padrão
                max_empresas = 1  # Valor padrão
                
                if limite_row:
                    max_cargos = limite_row[0] or max_cargos
                    max_empresas = limite_row[1] or max_empresas
                    
                # 2. Obter cargos dos participantes
                cargo_dentista = None
                cargo_usuario = None
                
                if dentista_id:
                    cargo_dentista = SplitService.obter_cargo_dentista(dentista_id)
                    logger.debug(f"Cargo do dentista ID={dentista_id}: {cargo_dentista}")
                    
                    # Verificar se o usuário do dentista tem integração válida
                    if cargo_dentista:
                        user_id_dentista = SplitService.obter_user_id_dentista(dentista_id)
                        if user_id_dentista:
                            cursor.execute("""
                                SELECT bempaggo_receiver_id, bempaggo_integration_status
                                FROM users
                                WHERE id = %s
                            """, (user_id_dentista,))
                            
                            user_info = cursor.fetchone()
                            if not user_info or not user_info[0] or user_info[1] not in ('integrado_por_cnpj', 'integrado_por_cpf'):
                                logger.debug(f"Usuário do dentista {user_id_dentista} não tem integração válida com Bempaggo")
                                cargo_dentista = None  # Anular cargo se usuário não tem integração
                        else:
                            logger.debug(f"Dentista ID={dentista_id} não tem usuário vinculado")
                            cargo_dentista = None
                
                if usuario_id:
                    cargo_usuario = SplitService.obter_cargo_usuario(usuario_id)
                    logger.debug(f"Cargo do usuário ID={usuario_id}: {cargo_usuario}")
                
                # 3. Montar conjunto de regras priorizadas
                split_manager = SplitManager()
                cargos_incluidos = set()
                
                # Variáveis para controlar valores fixos
                total_valores_fixos = Decimal('0')
                cargos_valor_fixo = []
                cargos_percentual = []
                
                # 3.1 Primeiro, incluir os cargos dos participantes diretos
                cargos_prioritarios = []
                
                # Verificar se o cargo do dentista está configurado para participar do split
                if cargo_dentista:
                    cursor.execute("""
                        SELECT 1
                        FROM participacao_cargo_split pcs
                        WHERE pcs.tipo_odontograma_id = %s
                          AND pcs.cargo_id = %s
                          AND pcs.ativo = TRUE
                        LIMIT 1
                    """, (tipo_odontograma_id, cargo_dentista))
                    
                    if cursor.fetchone():
                        cargos_prioritarios.append(cargo_dentista)
                        logger.debug(f"Cargo do dentista {cargo_dentista} está configurado para participar do split")
                    else:
                        logger.debug(f"Cargo do dentista {cargo_dentista} não está configurado para participar do split tipo {tipo_odontograma_id}")
                
                if cargo_usuario and cargo_usuario != cargo_dentista:
                    cargos_prioritarios.append(cargo_usuario)
                    
                    # Aplicar regras condicionais de split
                    if cargo_usuario in REGRAS_SPLIT_CONDICIONAL:
                        cargos_beneficiados = REGRAS_SPLIT_CONDICIONAL[cargo_usuario]
                        
                        # Processar cada cargo beneficiado
                        for cargo_beneficiado in cargos_beneficiados:
                            # Verificar se o cargo beneficiado está configurado para participar
                            cursor.execute("""
                                SELECT pcs.ativo, c.nome
                                FROM participacao_cargo_split pcs
                                JOIN cargos c ON pcs.cargo_id = c.id
                                WHERE pcs.tipo_odontograma_id = %s 
                                  AND pcs.cargo_id = %s
                                LIMIT 1
                            """, (tipo_odontograma_id, cargo_beneficiado))
                            
                            resultado = cursor.fetchone()
                            
                            if resultado and resultado[0]:  # Se existe e está ativo
                                cargos_prioritarios.append(cargo_beneficiado)
                                logger.info(
                                    f"Regra condicional aplicada: Vendedor cargo_id={cargo_usuario} "
                                    f"adiciona {resultado[1]} (ID={cargo_beneficiado}) ao split"
                                )
                            else:
                                logger.debug(
                                    f"Cargo beneficiado {cargo_beneficiado} não está ativo "
                                    f"para tipo_odontograma_id={tipo_odontograma_id}"
                                )
                
                logger.debug(f"Cargos prioritários: {cargos_prioritarios}")
                
                for cargo_id in cargos_prioritarios:
                    # Determinar qual usuário usar (priorizar o que está fazendo a venda)
                    user_id_to_use = None
                    if cargo_id == cargo_usuario and usuario_id:
                        user_id_to_use = usuario_id
                    elif cargo_id == cargo_dentista and dentista_id:
                        # Obter o user_id do dentista através da foreign key
                        user_id_to_use = SplitService.obter_user_id_dentista(dentista_id)
                    
                    # Buscar regra específica da unidade primeiro, depois a geral
                    cursor.execute("""
                        SELECT rs.id, rs.percentual, rs.tipo_calculo, rs.valor_fixo_brl,
                            rs.ciclos_participacao, rs.absorve_saldo,
                            u.bempaggo_receiver_id, c.nome, u.id AS user_id, rs.unidade
                        FROM regras_split rs
                        JOIN cargos c ON rs.cargo_id = c.id
                        LEFT JOIN users u ON u.cargo_id = rs.cargo_id 
                                        AND u.bempaggo_integration_status IN ('integrado_por_cnpj', 'integrado_por_cpf')
                                        AND u.bempaggo_receiver_id IS NOT NULL
                                        AND u.unidade = %s
                                        AND (CASE 
                                            WHEN %s IS NOT NULL THEN u.id = %s
                                            ELSE TRUE
                                        END)
                        WHERE rs.tipo_odontograma_id = %s 
                        AND rs.cargo_id = %s
                        AND rs.ativo = TRUE
                        AND (rs.unidade = %s OR rs.unidade IS NULL)
                        ORDER BY 
                            CASE WHEN rs.unidade IS NOT NULL THEN 1 ELSE 2 END,  -- Priorizar regras específicas
                            CASE WHEN %s IS NOT NULL AND u.id = %s THEN 1 ELSE 2 END,  -- Priorizar usuário específico
                            u.id
                        LIMIT 1
                    """, (unidade, user_id_to_use, user_id_to_use, tipo_odontograma_id, cargo_id, unidade, user_id_to_use, user_id_to_use))
                    
                    regra = cursor.fetchone()
                    
                    if regra:
                        regra_id, percentual, tipo_calculo, valor_fixo, ciclos, absorve, receiver_id, cargo_nome, user_id, unidade_regra = regra
                        
                        if not receiver_id:
                            logger.warning(f"Cargo '{cargo_nome}' (ID={cargo_id}) tem regra de split mas não tem usuário integrado com receiver_id")
                            continue
                        
                        if tipo_calculo == 'valor_fixo' and valor_total_venda:
                            # Calcular percentual baseado no valor da venda
                            # Converter para Decimal para evitar erro de tipo
                            percentual_calculado = (valor_fixo / Decimal(str(valor_total_venda))) * 100
                            # Arredondar para 2 casas decimais
                            percentual_calculado = float(round(percentual_calculado, 2))
                            total_valores_fixos += valor_fixo
                            
                            cargos_valor_fixo.append({
                                'receiver_id': receiver_id,
                                'percentual': percentual_calculado,
                                'valor_fixo': float(valor_fixo),
                                'ciclos': ciclos,
                                'absorve': absorve,
                                'cargo_id': cargo_id,
                                'user_id': user_id,
                                'cargo_nome': cargo_nome,
                                'tipo_calculo': 'valor_fixo'
                            })
                            logger.debug(f"Cargo '{cargo_nome}' com valor fixo: R$ {valor_fixo} = {percentual_calculado}%")
                        else:
                            # Cargo com percentual normal
                            cargos_percentual.append({
                                'receiver_id': receiver_id,
                                'percentual': float(percentual),
                                'ciclos': ciclos,
                                'absorve': absorve,
                                'cargo_id': cargo_id,
                                'user_id': user_id,
                                'cargo_nome': cargo_nome,
                                'tipo_calculo': 'percentual'
                            })
                            logger.debug(f"Cargo '{cargo_nome}' com percentual: {percentual}%")
                        
                        cargos_incluidos.add(cargo_id)
                        max_cargos -= 1
                    
                # 3.2 Complementar com cargos adicionais conforme prioridade configurada
                # IMPORTANTE: Se CRC está vendendo, não adicionar cargos complementares
                # (apenas CRC + Supervisor + Gerente da regra condicional)
                # Se Comercial está vendendo, não adicionar CRCs
                # Se Gerente ou Supervisor está vendendo, não adicionar cargos complementares
                deve_adicionar_complementares = True
                
                if cargo_usuario == CargoIDs.CRC:
                    logger.info("CRC vendendo - não adicionar cargos complementares além dos da regra condicional")
                    deve_adicionar_complementares = False
                elif cargo_usuario == CargoIDs.COMERCIAL:
                    logger.info("Comercial vendendo - não adicionar CRCs no split")
                    # Vamos adicionar complementares mas excluir CRCs
                    deve_adicionar_complementares = True
                elif cargo_usuario == CargoIDs.GERENTE:
                    logger.info("Gerente vendendo - apenas o gerente entra como cargo no split")
                    deve_adicionar_complementares = False
                elif cargo_usuario == CargoIDs.SUPERVISOR:
                    logger.info("Supervisor vendendo - apenas o supervisor entra como cargo no split")
                    deve_adicionar_complementares = False
                
                if max_cargos > 0 and deve_adicionar_complementares:
                    # Determinar cargos que devem ser excluídos baseado nas regras condicionais
                    cargos_excluidos_condicionais = set(cargos_incluidos)
                    
                    # Se Comercial está vendendo, excluir CRCs e Supervisor dos complementares
                    # (Gerente já é adicionado pela regra condicional)
                    if cargo_usuario == CargoIDs.COMERCIAL:
                        cargos_excluidos_condicionais.add(CargoIDs.CRC)
                        cargos_excluidos_condicionais.add(CargoIDs.SUPERVISOR)
                        logger.debug("Excluindo CRCs e Supervisor dos cargos complementares (Comercial vendendo)")
                    
                    placeholders = ','.join(['%s' for _ in cargos_excluidos_condicionais]) if cargos_excluidos_condicionais else "0"
                    exclude_params = list(cargos_excluidos_condicionais)
                    
                    query = f"""
                        SELECT rs.id, rs.cargo_id, rs.percentual, rs.tipo_calculo, rs.valor_fixo_brl,
                            rs.ciclos_participacao, rs.absorve_saldo,
                            u.bempaggo_receiver_id, c.nome, u.id AS user_id, rs.unidade
                        FROM regras_split rs
                        JOIN participacao_cargo_split pcs ON rs.cargo_id = pcs.cargo_id AND rs.tipo_odontograma_id = pcs.tipo_odontograma_id
                        JOIN cargos c ON rs.cargo_id = c.id
                        LEFT JOIN users u ON u.cargo_id = rs.cargo_id 
                                        AND u.bempaggo_integration_status IN ('integrado_por_cnpj', 'integrado_por_cpf')
                                        AND u.bempaggo_receiver_id IS NOT NULL
                                        AND u.unidade = %s
                        WHERE rs.tipo_odontograma_id = %s 
                        AND pcs.ativo = TRUE
                        AND rs.ativo = TRUE
                        AND (rs.unidade = %s OR rs.unidade IS NULL)
                    """
                    
                    params = [unidade, tipo_odontograma_id, unidade]
                    
                    if cargos_incluidos:
                        query += f" AND rs.cargo_id NOT IN ({placeholders})"
                        params.extend(exclude_params)
                    
                    query += """
                        GROUP BY rs.id, rs.cargo_id, rs.percentual, rs.tipo_calculo, rs.valor_fixo_brl,
                                 rs.ciclos_participacao, rs.absorve_saldo,
                                 u.bempaggo_receiver_id, c.nome, u.id, pcs.ordem_prioridade, rs.unidade
                        ORDER BY 
                            CASE WHEN rs.unidade IS NOT NULL THEN 1 ELSE 2 END,  -- Priorizar regras específicas
                            pcs.ordem_prioridade
                        LIMIT %s
                    """
                    
                    params.append(max_cargos)
                    
                    cursor.execute(query, params)
                    regras_complementares = cursor.fetchall()
                    
                    for regra in regras_complementares:
                        _, cargo_id, percentual, tipo_calculo, valor_fixo, ciclos, absorve, receiver_id, cargo_nome, user_id, unidade_regra = regra
                        
                        if not receiver_id:
                            logger.warning(f"Cargo '{cargo_nome}' (ID={cargo_id}) tem regra de split mas não tem usuário integrado com receiver_id")
                            continue
                        
                        if tipo_calculo == 'valor_fixo' and valor_total_venda:
                            # Calcular percentual baseado no valor da venda
                            # Converter para Decimal para evitar erro de tipo
                            percentual_calculado = (valor_fixo / Decimal(str(valor_total_venda))) * 100
                            # Arredondar para 2 casas decimais
                            percentual_calculado = float(round(percentual_calculado, 2))
                            total_valores_fixos += valor_fixo
                            
                            cargos_valor_fixo.append({
                                'receiver_id': receiver_id,
                                'percentual': percentual_calculado,
                                'valor_fixo': float(valor_fixo),
                                'ciclos': ciclos,
                                'absorve': absorve,
                                'cargo_id': cargo_id,
                                'user_id': user_id,
                                'cargo_nome': cargo_nome,
                                'tipo_calculo': 'valor_fixo'
                            })
                            logger.debug(f"Cargo complementar '{cargo_nome}' com valor fixo: R$ {valor_fixo} = {percentual_calculado}%")
                        else:
                            cargos_percentual.append({
                                'receiver_id': receiver_id,
                                'percentual': float(percentual),
                                'ciclos': ciclos,
                                'absorve': absorve,
                                'cargo_id': cargo_id,
                                'user_id': user_id,
                                'cargo_nome': cargo_nome,
                                'tipo_calculo': 'percentual'
                            })
                            logger.debug(f"Cargo complementar '{cargo_nome}' com percentual: {percentual}%")
                        
                        cargos_incluidos.add(cargo_id)
                
                # 3.3 Adicionar empresas se configurado
                empresas_valor_fixo = []
                empresas_percentual = []

                if max_empresas > 0:
                    cursor.execute("""
                        SELECT ers.id, ers.empresa_id, ers.percentual, ers.ciclos_participacao, ers.absorve_saldo,
                               e.bempaggo_receiver_id, e.razao_social, ers.unidade,
                               ers.tipo_calculo, ers.valor_fixo_brl
                        FROM empresa_regras_split ers
                        JOIN participacao_empresa_split pes ON ers.empresa_id = pes.empresa_id
                                                           AND ers.tipo_odontograma_id = pes.tipo_odontograma_id
                        JOIN empresas e ON ers.empresa_id = e.id
                        WHERE ers.tipo_odontograma_id = %s
                          AND ers.ativo = TRUE
                          AND pes.ativo = TRUE
                          AND e.bempaggo_receiver_id IS NOT NULL
                          AND (ers.unidade = %s OR ers.unidade IS NULL)
                        ORDER BY
                            CASE WHEN ers.unidade IS NOT NULL THEN 1 ELSE 2 END,  -- Priorizar regras específicas
                            pes.ordem_prioridade
                        LIMIT %s
                    """, (tipo_odontograma_id, unidade, max_empresas))

                    regras_empresas = cursor.fetchall()

                    # Separar empresas por tipo de cálculo
                    for regra in regras_empresas:
                        _, empresa_id, percentual, ciclos, absorve, receiver_id, razao_social, unidade_regra, tipo_calc, valor_fixo = regra

                        if not receiver_id:
                            logger.warning(f"Empresa '{razao_social}' (ID={empresa_id}) não tem receiver_id configurado")
                            continue

                        # APLICAR MAPEAMENTO ESPECÍFICO POR UNIDADE
                        receiver_id = SplitService.get_receiver_id_especifico(empresa_id, unidade, receiver_id)

                        empresa_data = {
                            'empresa_id': empresa_id,
                            'percentual': float(percentual),
                            'ciclos': ciclos,
                            'absorve': absorve,
                            'receiver_id': receiver_id,
                            'razao_social': razao_social,
                            'tipo_calculo': tipo_calc or 'percentual',
                            'valor_fixo': float(valor_fixo) if valor_fixo else None
                        }

                        if tipo_calc == 'valor_fixo' and valor_fixo:
                            # CALCULAR PERCENTUAL para empresas com valor fixo (mesma lógica dos cargos)
                            if valor_total_venda:
                                percentual_calculado = (valor_fixo / Decimal(str(valor_total_venda))) * 100
                                percentual_calculado = float(round(percentual_calculado, 2))
                            else:
                                percentual_calculado = 0

                            # Atualizar empresa_data com o percentual calculado
                            empresa_data['percentual'] = percentual_calculado

                            empresas_valor_fixo.append(empresa_data)
                            total_valores_fixos += Decimal(str(valor_fixo))
                            logger.info(f"Empresa '{razao_social}' com valor fixo R${valor_fixo:.2f} = {percentual_calculado:.2f}%")
                        else:
                            empresas_percentual.append(empresa_data)
                            logger.debug(f"Empresa '{razao_social}' com percentual: {percentual}%")
                
                # 3.4 Verificar se valores fixos não excedem o valor da venda
                if valor_total_venda and total_valores_fixos > Decimal(str(valor_total_venda)):
                    logger.error(f"Valores fixos ({total_valores_fixos}) excedem valor da venda ({valor_total_venda})")
                    raise ValueError("Soma dos valores fixos excede o valor total da venda")
                
                # 3.5 Calcular percentual disponível para splits percentuais
                percentual_disponivel = 100.0
                if valor_total_venda and total_valores_fixos > 0:
                    # Converter para Decimal para evitar erro de tipo
                    percentual_usado_valores_fixos = float((total_valores_fixos / Decimal(str(valor_total_venda))) * 100)
                    percentual_disponivel = 100.0 - percentual_usado_valores_fixos
                    logger.info(f"Percentual usado por valores fixos: {percentual_usado_valores_fixos:.2f}%, disponível: {percentual_disponivel:.2f}%")

                    # VALIDAÇÃO CRÍTICA: Impedir processamento se valores fixos excederem 100%
                    if percentual_usado_valores_fixos >= 100.0:
                        logger.error(f"VALORES FIXOS EXCEDEM 100% DA VENDA: {percentual_usado_valores_fixos:.2f}% - CANCELANDO PROCESSAMENTO")
                        raise ValueError(f"Valores fixos excedem 100% do valor da venda ({percentual_usado_valores_fixos:.2f}%)")
                
                # 3.6 Adicionar cargos com valor fixo ao split_manager
                for cargo_fixo in cargos_valor_fixo:
                    split_manager.add_split(
                        seller_id=cargo_fixo['receiver_id'],
                        percentage=cargo_fixo['percentual'],
                        cycles_to_participate=cargo_fixo['ciclos'],
                        absorb_balance=cargo_fixo['absorve'],
                        cargo_id=cargo_fixo['cargo_id'],
                        user_id=cargo_fixo['user_id']
                    )
                
                # 3.7 Ajustar percentuais dos cargos com percentual para caber no disponível
                if cargos_percentual and percentual_disponivel < 100.0:
                    # Calcular total dos percentuais originais
                    total_percentual_original = sum(c['percentual'] for c in cargos_percentual)
                    if total_percentual_original > 0:
                        fator_ajuste = percentual_disponivel / total_percentual_original
                        logger.info(f"Ajustando percentuais com fator: {fator_ajuste:.4f}")
                        
                        for cargo in cargos_percentual:
                            # Arredondar após aplicar o fator de ajuste
                            cargo['percentual'] = round(cargo['percentual'] * fator_ajuste, 2)
                            logger.debug(f"Cargo '{cargo['cargo_nome']}' ajustado para: {cargo['percentual']}%")
                
                # 3.8 Adicionar cargos com percentual ajustado
                for cargo in cargos_percentual:
                    split_manager.add_split(
                        seller_id=cargo['receiver_id'],
                        percentage=cargo['percentual'],
                        cycles_to_participate=cargo['ciclos'],
                        absorb_balance=cargo['absorve'],
                        cargo_id=cargo['cargo_id'],
                        user_id=cargo['user_id']
                    )

                # 3.9 Adicionar empresas com valor fixo ao split_manager
                for empresa_fixo in empresas_valor_fixo:
                    # JÁ CALCULADO ANTERIORMENTE: Usar percentual pré-calculado para evitar dupla conversão
                    percentual_empresa = empresa_fixo.get('percentual', 0)

                    # LOG MELHORADO: Informar sobre o processamento para evitar confusão
                    logger.info(f"Empresa '{empresa_fixo['razao_social']}' processada com percentual pré-calculado: {percentual_empresa:.2f}% (R${empresa_fixo['valor_fixo']:.2f})")

                    split_manager.add_split(
                        seller_id=empresa_fixo['receiver_id'],
                        percentage=float(percentual_empresa),
                        cycles_to_participate=empresa_fixo['ciclos'],
                        absorb_balance=empresa_fixo['absorve'],
                        empresa_id=empresa_fixo['empresa_id']
                    )

                # 3.10 Adicionar empresas com percentual
                for empresa in empresas_percentual:
                    split_manager.add_split(
                        seller_id=empresa['receiver_id'],
                        percentage=empresa['percentual'],
                        cycles_to_participate=empresa['ciclos'],
                        absorb_balance=empresa['absorve'],
                        empresa_id=empresa['empresa_id']
                    )
                    logger.debug(f"Empresa '{empresa['razao_social']}' com percentual: {empresa['percentual']}%")
                
                # 4. Validar e ajustar percentuais
                splits = split_manager.get_splits()
                
                if not splits:
                    logger.warning(f"Nenhuma regra de split aplicável encontrada para tipo_odontograma_id={tipo_odontograma_id}")
                    # Sem participantes válidos, retornar ao método antigo
                    return SplitService.obter_splits_para_tipo_odontograma(tipo_odontograma_id, unidade)
                
                # Verificar se os percentuais somam 100%
                total_percentual = sum(float(split["percentage"]) for split in splits)
                
                if abs(total_percentual - 100.0) > 0.01:
                    logger.warning(f"Percentuais dos splits não somam 100%, atual: {total_percentual}%. Ajustando...")
                    
                    # Buscar o split com absorve_saldo=True, ou o primeiro se nenhum
                    ajuste_idx = next((i for i, s in enumerate(splits) if s.get("absorbBalance")), 0)
                    ajuste = 100.0 - total_percentual
                    splits[ajuste_idx]["percentage"] += ajuste
                    
                    logger.debug(f"Split {ajuste_idx} ajustado em {ajuste}%: agora {splits[ajuste_idx]['percentage']}%")
                
                # Garantir precisão de 2 casas decimais e que a soma seja exatamente 100%
                # Arredondar todos os percentuais para 2 casas decimais
                for split in splits:
                    split["percentage"] = round(split["percentage"], 2)
                
                # Recalcular o total após arredondamento
                total_arredondado = sum(float(split["percentage"]) for split in splits)
                
                # Se ainda houver diferença devido ao arredondamento, ajustar no split que absorve saldo
                if total_arredondado != 100.0:
                    ajuste_idx = next((i for i, s in enumerate(splits) if s.get("absorbBalance")), 0)
                    diferenca = round(100.0 - total_arredondado, 2)
                    splits[ajuste_idx]["percentage"] = round(splits[ajuste_idx]["percentage"] + diferenca, 2)
                    logger.debug(f"Ajuste final de precisão: {diferenca}% no split {ajuste_idx}")
                
                # VALIDAÇÃO FINAL ROBUSTA
                total_final = sum(float(split["percentage"]) for split in splits)
                logger.info(f"Total final dos percentuais: {total_final}%")

                # VALIDAÇÃO CRÍTICA: Bloquear splits incorretos
                if abs(total_final - 100.0) > 0.01:
                    logger.error(f"ERRO CRÍTICO: Soma dos percentuais = {total_final}% (deveria ser 100%)")
                    logger.error(f"Splits detalhados: {splits}")
                    raise ValueError(f"Soma dos percentuais inválida: {total_final}% (esperado: 100%)")

                # Log detalhado para auditoria
                logger.info(f"CONFIGURAÇÃO DE SPLIT VALIDADA COM SUCESSO: {len(splits)} participantes")
                for i, split in enumerate(splits):
                    logger.info(f"  Split {i+1}: SellerID {split.get('seller_id', 'N/A')} = {split['percentage']}%")

                if incluir_metadata:
                    return split_manager.get_splits_with_metadata()

                return splits
                
        except Exception as e:
            logger.error(f"Erro ao determinar splits dinâmicos: {str(e)}", exc_info=True)
            # Em caso de erro, tentar o método antigo como fallback
            return SplitService.obter_splits_para_tipo_odontograma(tipo_odontograma_id, unidade)
            
    @staticmethod
    def obter_splits_com_entrada_separada(
        tipo_odontograma_id: int,
        dentista_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        valor_entrada: Optional[Decimal] = None,
        valor_parcelas: Optional[Decimal] = None,
        unidade: Optional[str] = None,
        incluir_metadata: bool = False
    ) -> Dict[str, Optional[List[Dict[str, Any]]]]:
        """
        Obtém splits separados para entrada e parcelas.
        - Split da entrada: todos os participantes (cargos + empresas)
        - Split das parcelas: participantes com ciclos restantes após a entrada
        
        Args:
            tipo_odontograma_id: ID do tipo de odontograma
            dentista_id: ID do dentista orcamentista
            usuario_id: ID do usuário realizando a venda
            valor_entrada: Valor da entrada para cálculo de percentuais
            valor_parcelas: Valor total das parcelas para cálculo de percentuais
            unidade: Unidade específica para buscar regras
            
        Returns:
            Dict com 'entrada' e 'parcelas' contendo listas de splits
        """
        logger.info(f"Obtendo splits separados para entrada/parcelas: tipo={tipo_odontograma_id}, entrada=R${valor_entrada}, parcelas=R${valor_parcelas}")
        
        # Split da entrada: todos os participantes
        splits_entrada = None
        if valor_entrada and valor_entrada > 0:
            splits_entrada = SplitService.obter_splits_para_venda(
                tipo_odontograma_id=tipo_odontograma_id,
                dentista_id=dentista_id,
                usuario_id=usuario_id,
                valor_total_venda=valor_entrada,
                unidade=unidade,
                incluir_metadata=incluir_metadata
            )
            logger.info(f"Splits para entrada (todos participantes): {len(splits_entrada) if splits_entrada else 0} participantes")
        
        # Split das parcelas: entrada consome o primeiro ciclo dos participantes
        splits_parcelas = None
        if valor_parcelas and valor_parcelas > 0:
            splits_parcelas = SplitService.obter_splits_para_parcelas_pos_entrada(
                tipo_odontograma_id=tipo_odontograma_id,
                dentista_id=dentista_id,
                usuario_id=usuario_id,
                valor_total_venda=valor_parcelas,
                unidade=unidade,
                incluir_metadata=incluir_metadata
            )
            logger.info(f"Splits para parcelas pós-entrada: {len(splits_parcelas) if splits_parcelas else 0} participantes")
        
        return {
            'entrada': splits_entrada,
            'parcelas': splits_parcelas
        }

    @staticmethod
    def verificar_venda_tem_entrada(venda_id: int) -> bool:
        """
        Verifica se uma venda possui entrada configurada.
        
        Args:
            venda_id: ID da venda
            
        Returns:
            True se a venda tem entrada, False caso contrário
        """
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT v.valor_entrada, v.valor_taxa_adesao, v.entrada_automatica,
                           v.tipo_cobranca_inicial, v.pre_venda_id,
                           pve.valor_solicitado
                    FROM vendas v
                    LEFT JOIN pre_vendas_entradas pve ON pve.pre_venda_id = v.pre_venda_id
                    WHERE v.id = %s
                    LIMIT 1
                """, (venda_id,))
                
                row = cursor.fetchone()
                if row:
                    valor_entrada, valor_taxa_adesao, entrada_automatica, tipo_cobranca_inicial, pre_venda_id, valor_pre_venda = row
                    
                    # Tem entrada/taxa separada se há valor na venda, flag automática,
                    # tipo inicial separado ou entrada registrada na pré-venda.
                    tem_entrada = (
                        (valor_entrada and valor_entrada > 0) or
                        (valor_taxa_adesao and valor_taxa_adesao > 0) or
                        entrada_automatica or
                        tipo_cobranca_inicial in ('entrada', 'taxa_adesao') or
                        (valor_pre_venda and valor_pre_venda > 0)
                    )
                    
                    logger.info(
                        "Venda %s tem entrada/taxa separada: %s (entrada=%s, taxa=%s, auto=%s, tipo=%s, pre_venda_id=%s, valor_pre_venda=%s)",
                        venda_id,
                        tem_entrada,
                        valor_entrada,
                        valor_taxa_adesao,
                        entrada_automatica,
                        tipo_cobranca_inicial,
                        pre_venda_id,
                        valor_pre_venda
                    )
                    return tem_entrada
                    
                return False
                
        except Exception as e:
            logger.error(f"Erro ao verificar entrada da venda {venda_id}: {str(e)}")
            return False

    @staticmethod
    def obter_splits_para_parcelas_pos_entrada(
        tipo_odontograma_id: int,
        dentista_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        valor_total_venda: Optional[Decimal] = None,
        unidade: Optional[str] = None,
        incluir_metadata: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtém splits para parcelas/faturas posteriores a uma entrada.

        A entrada já consome o primeiro ciclo. Portanto:
        - splits com 1 ciclo não entram nas parcelas;
        - splits com N ciclos entram por N-1 parcelas;
        - splits recorrentes/contínuos, como empresas com 999 ciclos, permanecem.
        """
        logger.info(
            "Obtendo splits pós-entrada: tipo=%s, dentista=%s, usuario=%s, valor=%s, unidade=%s",
            tipo_odontograma_id,
            dentista_id,
            usuario_id,
            valor_total_venda,
            unidade
        )

        try:
            splits_completos = SplitService.obter_splits_para_venda(
                tipo_odontograma_id=tipo_odontograma_id,
                dentista_id=dentista_id,
                usuario_id=usuario_id,
                valor_total_venda=valor_total_venda,
                unidade=unidade,
                incluir_metadata=incluir_metadata
            )

            if not splits_completos:
                logger.warning("Não foi possível obter split completo para pós-entrada. Usando apenas empresas como fallback.")
                return SplitService.obter_splits_apenas_empresas(
                    tipo_odontograma_id=tipo_odontograma_id,
                    unidade=unidade,
                    valor_total_venda=valor_total_venda
                )

            splits_parcelas = []
            percentual_removido = Decimal("0")

            for split in splits_completos:
                split_parcela = split.copy()
                percentual = Decimal(str(split_parcela.get("percentage", 0)))

                try:
                    ciclos = int(split_parcela.get("cyclesToParticipate", 0))
                except (TypeError, ValueError):
                    logger.warning("Split sem cyclesToParticipate válido tratado como 1 ciclo: %s", split_parcela)
                    ciclos = 1

                if ciclos <= 1:
                    percentual_removido += percentual
                    logger.info(
                        "Split sellerId=%s removido das parcelas pós-entrada: ciclos=%s, percentual=%s",
                        split_parcela.get("sellerId"),
                        ciclos,
                        percentual
                    )
                    continue

                if ciclos < 999:
                    split_parcela["cyclesToParticipate"] = ciclos - 1

                splits_parcelas.append(split_parcela)

            if not splits_parcelas:
                logger.warning("Todos os splits foram consumidos pela entrada. Usando apenas empresas como fallback.")
                return SplitService.obter_splits_apenas_empresas(
                    tipo_odontograma_id=tipo_odontograma_id,
                    unidade=unidade,
                    valor_total_venda=valor_total_venda
                )

            ajuste_idx = next((i for i, s in enumerate(splits_parcelas) if s.get("absorbBalance")), 0)

            if percentual_removido:
                percentual_atual = Decimal(str(splits_parcelas[ajuste_idx].get("percentage", 0)))
                splits_parcelas[ajuste_idx]["percentage"] = float(percentual_atual + percentual_removido)
                logger.info(
                    "Percentual removido pela entrada (%s%%) realocado para sellerId=%s",
                    percentual_removido,
                    splits_parcelas[ajuste_idx].get("sellerId")
                )

            for split in splits_parcelas:
                split["percentage"] = round(float(split["percentage"]), 2)

            total_arredondado = round(sum(float(split["percentage"]) for split in splits_parcelas), 2)
            if total_arredondado != 100.0:
                diferenca = round(100.0 - total_arredondado, 2)
                splits_parcelas[ajuste_idx]["percentage"] = round(
                    float(splits_parcelas[ajuste_idx]["percentage"]) + diferenca,
                    2
                )
                logger.debug("Ajuste final pós-entrada: %s%% no split %s", diferenca, ajuste_idx)

            total_final = sum(float(split["percentage"]) for split in splits_parcelas)
            if abs(total_final - 100.0) > 0.01:
                logger.error("Soma inválida dos splits pós-entrada: %s%%. Splits: %s", total_final, splits_parcelas)
                return None

            logger.info("Configuração de split pós-entrada: %s participantes", len(splits_parcelas))
            return splits_parcelas

        except Exception as e:
            logger.error(f"Erro ao obter splits pós-entrada: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def obter_splits_apenas_empresas(
        tipo_odontograma_id: int,
        unidade: Optional[str] = None,
        valor_total_venda: Optional[Decimal] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtém splits configurados apenas para empresas (sem cargos/usuários).
        Usado quando há entrada e o split das parcelas deve ser apenas entre empresas.

        Args:
            tipo_odontograma_id: ID do tipo de odontograma
            unidade: Unidade específica para buscar regras
            valor_total_venda: Valor total da venda para conversão de valores fixos

        Returns:
            Lista de splits apenas de empresas ou None se não encontrar
        """
        logger.info(f"Obtendo splits apenas de empresas para tipo_odontograma_id={tipo_odontograma_id}, unidade={unidade}, valor={valor_total_venda}")
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar apenas empresas participantes
                cursor.execute("""
                    SELECT ers.empresa_id, ers.percentual, ers.ciclos_participacao, ers.absorve_saldo,
                           e.bempaggo_receiver_id, e.razao_social,
                           ers.tipo_calculo, ers.valor_fixo_brl
                    FROM empresa_regras_split ers
                    JOIN participacao_empresa_split pes ON ers.empresa_id = pes.empresa_id
                                                       AND ers.tipo_odontograma_id = pes.tipo_odontograma_id
                    JOIN empresas e ON ers.empresa_id = e.id
                    WHERE ers.tipo_odontograma_id = %s
                      AND ers.ativo = TRUE
                      AND pes.ativo = TRUE
                      AND e.bempaggo_receiver_id IS NOT NULL
                      AND e.bempaggo_integration_status = 'integrado_por_cnpj'
                      AND (ers.unidade = %s OR ers.unidade IS NULL)
                    ORDER BY
                        CASE WHEN ers.unidade IS NOT NULL THEN 1 ELSE 2 END,
                        pes.ordem_prioridade
                """, (tipo_odontograma_id, unidade))

                empresas_rows = cursor.fetchall()

                if not empresas_rows:
                    logger.warning(f"Nenhuma empresa configurada para splits do tipo_odontograma_id={tipo_odontograma_id}")
                    return None

                # Configurar SplitManager
                split_manager = SplitManager()

                # Separar empresas por tipo de cálculo
                empresas_valor_fixo = []
                empresas_percentual = []
                total_valores_fixos = Decimal('0')

                for row in empresas_rows:
                    empresa_id, percentual, ciclos, absorve, receiver_id, razao_social, tipo_calc, valor_fixo = row

                    # APLICAR MAPEAMENTO ESPECÍFICO POR UNIDADE
                    receiver_id = SplitService.get_receiver_id_especifico(empresa_id, unidade, receiver_id)

                    empresa_data = {
                        'empresa_id': empresa_id,
                        'percentual': float(percentual),
                        'ciclos': ciclos,
                        'absorve': absorve,
                        'receiver_id': receiver_id,
                        'razao_social': razao_social,
                        'tipo_calculo': tipo_calc or 'percentual',
                        'valor_fixo': float(valor_fixo) if valor_fixo else None
                    }

                    if tipo_calc == 'valor_fixo' and valor_fixo:
                        empresas_valor_fixo.append(empresa_data)
                        total_valores_fixos += Decimal(str(valor_fixo))
                        logger.info(f"Empresa '{razao_social}' com valor fixo: R${valor_fixo:.2f}")
                    else:
                        empresas_percentual.append(empresa_data)
                        logger.debug(f"Empresa '{razao_social}' com percentual: {percentual}%")

                # Adicionar empresas com valor fixo
                for empresa_fixo in empresas_valor_fixo:
                    # Converter valor fixo para percentual baseado no valor total
                    if valor_total_venda and valor_total_venda > 0:
                        percentual_empresa = (Decimal(str(empresa_fixo['valor_fixo'])) / Decimal(str(valor_total_venda))) * 100
                    else:
                        percentual_empresa = Decimal(str(empresa_fixo['percentual']))

                    # Arredondar para 2 casas decimais antes de adicionar
                    percentual_arredondado = round(float(percentual_empresa), 2)

                    split_manager.add_split(
                        seller_id=empresa_fixo['receiver_id'],
                        percentage=percentual_arredondado,
                        cycles_to_participate=empresa_fixo['ciclos'],
                        absorb_balance=empresa_fixo['absorve']
                    )
                    logger.info(f"Empresa '{empresa_fixo['razao_social']}' com valor fixo R${empresa_fixo['valor_fixo']:.2f} = {percentual_arredondado}%")

                # Adicionar empresas com percentual
                for empresa in empresas_percentual:
                    split_manager.add_split(
                        seller_id=empresa['receiver_id'],
                        percentage=empresa['percentual'],
                        cycles_to_participate=empresa['ciclos'],
                        absorb_balance=empresa['absorve']
                    )
                    logger.debug(f"Empresa '{empresa['razao_social']}' com percentual: {empresa['percentual']}%")
                
                # Validar se os percentuais somam 100%
                splits = split_manager.get_splits()
                total_percentual = sum(float(split["percentage"]) for split in splits)

                if abs(total_percentual - 100.0) > 0.01:
                    logger.warning(f"Percentuais das empresas não somam 100%, atual: {total_percentual}%. Ajustando...")
                    logger.info(f"Splits antes do ajuste: {splits}")

                    # Buscar o split com absorve_saldo=True, ou o primeiro se nenhum
                    ajuste_idx = next((i for i, s in enumerate(splits) if s.get("absorbBalance")), 0)
                    logger.info(f"Índice do split para ajuste: {ajuste_idx}")
                    ajuste = 100.0 - total_percentual
                    novo_percentual = round(splits[ajuste_idx]["percentage"] + ajuste, 2)

                    # Atualizar o split_manager diretamente para que a mudança persista
                    split_manager.update_split(ajuste_idx, percentage=novo_percentual)
                    logger.info(f"Split {ajuste_idx} ajustado em {ajuste}%: agora {novo_percentual}%")

                splits_finais = split_manager.get_splits()
                logger.info(f"Configuração de split apenas empresas: {len(splits_finais)} participantes")
                
                return splits_finais
                
        except Exception as e:
            logger.error(f"Erro ao obter splits apenas de empresas: {str(e)}", exc_info=True)
            return None
