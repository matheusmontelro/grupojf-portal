# app/users_sdk/receiver_api.py

import logging
import json
import time
from requests.exceptions import RequestException
from .http_client import HttpClientFactory
from .environment import Environment
from .exceptions import BempaggoAPIError, BempaggoConnectionError, BempaggoValidationError

logger = logging.getLogger(__name__)

class ReceiverAPI:
    """
    API client para gerenciar recebedores na BemPaggo.
    """

    def __init__(self, api_token, seller_id, environment="sandbox"):
        """
        Inicializa o cliente de API para recebedores.

        Args:
            api_token (str): Token de autenticação da API.
            seller_id (str): ID do vendedor na BemPaggo.
            environment (str): "sandbox" ou "production".
        """
        self.api_token = api_token
        self.seller_id = seller_id
        self.base_url = Environment.get_base_url(environment)
        self.http_client = HttpClientFactory.create(api_token)
        self.environment = environment
        
        logger.debug(f"ReceiverAPI inicializada em ambiente: {environment}")

    def create_receiver(self, receiver_data):
        """
        Cria um novo recebedor pessoa física na BemPaggo.
        Se a resposta 201 não incluir um ID, busca o ID usando o CPF.

        Args:
            receiver_data (dict): Dados do recebedor conforme requisitos da API.

        Returns:
            dict: Resposta da API contendo dados do recebedor criado.

        Raises:
            BempaggoAPIError: Erro retornado pela API.
            BempaggoConnectionError: Erro de conexão com a API.
            BempaggoValidationError: Dados inválidos para a API.
        """
        endpoint = f"{self.base_url}/receivers/cpf"
        
        # Extrair CPF para uso posterior na busca
        cpf = receiver_data.get('document')
        if not cpf:
            logger.error("CPF ausente nos dados do recebedor")
            raise BempaggoValidationError(["Document/CPF is required"])
        
        logger.info(f"Criando recebedor na BemPaggo para CPF {cpf}")
        
        try:
            response = self.http_client.post(endpoint, json=receiver_data)
            logger.debug(f"Status code: {response.status_code}")
            
            # Verificar se a resposta foi bem-sucedida (200 OK ou 201 Created)
            if response.status_code == 201 or response.status_code == 200:
                result = {}
                
                # Tentar decodificar como JSON
                try:
                    result = response.json()
                    logger.info(f"Recebedor criado com sucesso. Resposta: {result}")
                except json.JSONDecodeError:
                    logger.warning(f"Não foi possível decodificar JSON. Resposta texto: {response.text}")
                    # Criar resultado artificial para indicar sucesso
                    result = {"success": True, "text_response": response.text}
                
                # Se a resposta não tem 'id', buscar pelo CPF
                if 'id' not in result or not result.get('id'):
                    logger.info(f"ID não encontrado na resposta. Buscando pelo CPF: {cpf}")
                    
                    # Buscar recebedor pelo CPF com múltiplas tentativas
                    receiver = self._fetch_receiver_with_retries(cpf)
                    
                    if receiver and 'id' in receiver:
                        logger.info(f"Recebedor encontrado pelo CPF. ID: {receiver['id']}")
                        result['id'] = receiver['id']
                        result['found_by_cpf'] = True
                    else:
                        logger.warning(f"Recebedor não encontrado pelo CPF após todas as tentativas.")
                        result['id'] = f"temp_{cpf}_{int(time.time())}"
                        result['status'] = 'id_pendente'
                
                return result
            
            # Tratar erros específicos
            if response.status_code == 400:
                # Erro de validação
                try:
                    error_data = response.json()
                    logger.error(f"Erro de validação: {error_data}")
                    
                    # Verificar o tipo de error_data
                    if isinstance(error_data, list):
                        raise BempaggoValidationError(error_data)
                    else:
                        raise BempaggoValidationError(error_data.get('errors', []))
                        
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta de erro: {response.text}")
                    raise BempaggoAPIError(
                        response.status_code,
                        response.text,
                        "Erro de validação"
                    )
            
            # Erro genérico da API
            logger.error(f"Erro da API: {response.status_code} - {response.text}")
            raise BempaggoAPIError(
                response.status_code,
                response.text,
                "Erro ao criar recebedor"
            )
            
        except RequestException as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise BempaggoConnectionError(f"Erro ao conectar com a API: {str(e)}")
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
            raise

    def _fetch_receiver_with_retries(self, cpf, max_retries=3, initial_wait=2):
        """
        Tenta buscar o recebedor pelo CPF várias vezes, com espera incremental.
        
        Args:
            cpf (str): CPF do recebedor
            max_retries (int): Número máximo de tentativas
            initial_wait (int): Tempo de espera inicial em segundos
            
        Returns:
            dict: Dados do recebedor ou None se não encontrado
        """
        wait_time = initial_wait
        
        for attempt in range(max_retries):
            # Esperar antes de tentar - a primeira chamada também espera para dar
            # tempo ao sistema remoto processar o registro anterior
            logger.info(f"Aguardando {wait_time}s antes da tentativa {attempt+1} de buscar o CPF")
            time.sleep(wait_time)
            
            # Buscar recebedor pelo CPF
            receiver = self.get_receiver_by_cpf(cpf)
            
            if receiver and 'id' in receiver:
                logger.info(f"Recebedor encontrado na tentativa {attempt+1}. ID: {receiver['id']}")
                return receiver
                
            # Aumentar tempo de espera para próxima tentativa
            wait_time *= 1.5
            
        logger.warning(f"Recebedor não encontrado após {max_retries} tentativas")
        return None

    def get_receiver_by_cpf(self, cpf):
        """
        Busca um recebedor pelo CPF.
        """
        if not cpf:
            logger.warning("CPF vazio fornecido para busca")
            return None
            
        endpoint = f"{self.base_url}/receivers?searchField={cpf}"
        
        logger.info(f"Consultando recebedor por CPF: {cpf}")
        
        try:
            response = self.http_client.get(endpoint)
            logger.debug(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Verificar se retornou algum resultado
                    if result and isinstance(result, list) and len(result) > 0:
                        logger.info(f"Recebedor encontrado com CPF {cpf}: {result[0].get('id')}")
                        return result[0]  # Retorna o primeiro recebedor encontrado
                    else:
                        logger.info(f"Nenhum recebedor encontrado com o CPF: {cpf}")
                        return None
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta: {response.text}")
                    return None
            
            # Tratamento específico para outros status codes
            if response.status_code == 404:
                logger.info(f"API retornou 404 para CPF {cpf} - recebedor não existe")
                return None
                
            logger.warning(f"API retornou status inesperado: {response.status_code} para CPF {cpf}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar recebedor por CPF: {str(e)}")
            return None

    def get_receiver(self, receiver_id):
        """
        Busca um recebedor pelo ID.

        Args:
            receiver_id (str): ID do recebedor.

        Returns:
            dict: Dados do recebedor.

        Raises:
            BempaggoAPIError: Erro retornado pela API.
            BempaggoConnectionError: Erro de conexão com a API.
        """
        endpoint = f"{self.base_url}/receivers/{receiver_id}"
        
        logger.info(f"Consultando recebedor: {endpoint}")
        
        try:
            response = self.http_client.get(endpoint)
            logger.debug(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    return result
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta: {response.text}")
                    raise BempaggoAPIError(
                        response.status_code,
                        response.text,
                        "Resposta inválida da API"
                    )
            
            if response.status_code == 404:
                logger.warning(f"Recebedor não encontrado: {receiver_id}")
                return None
            
            logger.error(f"Erro da API: {response.status_code} - {response.text}")
            raise BempaggoAPIError(
                response.status_code,
                response.text,
                "Erro ao consultar recebedor"
            )
            
        except RequestException as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise BempaggoConnectionError(f"Erro ao conectar com a API: {str(e)}")
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            raise

    def update_receiver(self, receiver_id, receiver_data):
        """
        Atualiza os dados de um recebedor existente.

        Args:
            receiver_id (str): ID do recebedor.
            receiver_data (dict): Novos dados do recebedor.

        Returns:
            dict: Dados atualizados do recebedor.

        Raises:
            BempaggoAPIError: Erro retornado pela API.
            BempaggoConnectionError: Erro de conexão com a API.
            BempaggoValidationError: Dados inválidos para a API.
        """
        endpoint = f"{self.base_url}/receivers/{receiver_id}"
        
        logger.info(f"Atualizando recebedor: {endpoint}")
        logger.debug(f"Payload: {json.dumps(receiver_data)}")
        
        try:
            response = self.http_client.put(endpoint, json=receiver_data)
            logger.debug(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.info(f"Recebedor atualizado com sucesso: {receiver_id}")
                    return result
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta: {response.text}")
                    raise BempaggoAPIError(
                        response.status_code,
                        response.text,
                        "Resposta inválida da API"
                    )
            
            # Tratar erros específicos
            if response.status_code == 400:
                # Erro de validação
                try:
                    error_data = response.json()
                    logger.error(f"Erro de validação: {error_data}")
                    
                    # Verificar o tipo de error_data
                    if isinstance(error_data, list):
                        raise BempaggoValidationError(error_data)
                    else:
                        raise BempaggoValidationError(error_data.get('errors', []))
                        
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta de erro: {response.text}")
                    raise BempaggoAPIError(
                        response.status_code,
                        response.text,
                        "Erro de validação"
                    )
            
            if response.status_code == 404:
                logger.warning(f"Recebedor não encontrado: {receiver_id}")
                raise BempaggoAPIError(
                    response.status_code,
                    response.text,
                    f"Recebedor {receiver_id} não encontrado"
                )
            
            logger.error(f"Erro da API: {response.status_code} - {response.text}")
            raise BempaggoAPIError(
                response.status_code,
                response.text,
                "Erro ao atualizar recebedor"
            )
            
        except RequestException as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise BempaggoConnectionError(f"Erro ao conectar com a API: {str(e)}")
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            raise

    def create_company(self, company_data):
        """
        Cria uma nova empresa (pessoa jurídica) na BemPaggo.
        Se a resposta 201 não incluir um ID, busca o ID usando o CNPJ.

        Args:
            company_data (dict): Dados da empresa conforme requisitos da API.

        Returns:
            dict: Resposta da API contendo dados da empresa criada.

        Raises:
            BempaggoAPIError: Erro retornado pela API.
            BempaggoConnectionError: Erro de conexão com a API.
            BempaggoValidationError: Dados inválidos para a API.
        """
        endpoint = f"{self.base_url}/receivers/cnpj"
        
        # Extrair CNPJ para uso posterior na busca
        cnpj = company_data.get('document')
        if not cnpj:
            logger.error("CNPJ ausente nos dados da empresa")
            raise BempaggoValidationError(["Document/CNPJ is required"])
        
        logger.info(f"Criando empresa na BemPaggo para CNPJ {cnpj}")
        
        try:
            response = self.http_client.post(endpoint, json=company_data)
            logger.debug(f"Status code: {response.status_code}")
            
            # Verificar se a resposta foi bem-sucedida
            if response.status_code == 201 or response.status_code == 200:
                result = {}
                
                # Tentar decodificar como JSON
                try:
                    result = response.json()
                    logger.info(f"Empresa criada com sucesso. Resposta: {result}")
                except json.JSONDecodeError:
                    logger.warning(f"Não foi possível decodificar JSON. Resposta texto: {response.text}")
                    # Criar resultado artificial para indicar sucesso
                    result = {"success": True, "text_response": response.text}
                
                # Se a resposta não tem 'id', buscar pelo CNPJ
                if 'id' not in result or not result.get('id'):
                    logger.info(f"ID não encontrado na resposta. Buscando pelo CNPJ: {cnpj}")
                    
                    # Buscar empresa pelo CNPJ com múltiplas tentativas
                    company = self._fetch_company_with_retries(cnpj)
                    
                    if company and 'id' in company:
                        logger.info(f"Empresa encontrada pelo CNPJ. ID: {company['id']}")
                        result['id'] = company['id']
                        result['found_by_cnpj'] = True
                    else:
                        logger.warning(f"Empresa não encontrada pelo CNPJ após todas as tentativas.")
                        result['id'] = f"temp_{cnpj}_{int(time.time())}"
                        result['status'] = 'id_pendente'
                
                return result
            
            # Tratar erros específicos
            if response.status_code == 400:
                # Erro de validação
                try:
                    error_data = response.json()
                    logger.error(f"Erro de validação: {error_data}")
                    
                    # Verificar o tipo de error_data
                    if isinstance(error_data, list):
                        raise BempaggoValidationError(error_data)
                    else:
                        raise BempaggoValidationError(error_data.get('errors', []))
                        
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta de erro: {response.text}")
                    raise BempaggoAPIError(
                        response.status_code,
                        response.text,
                        "Erro de validação"
                    )
            
            # Erro genérico da API
            logger.error(f"Erro da API: {response.status_code} - {response.text}")
            raise BempaggoAPIError(
                response.status_code,
                response.text,
                "Erro ao criar empresa"
            )
            
        except RequestException as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise BempaggoConnectionError(f"Erro ao conectar com a API: {str(e)}")
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
            raise

    def _fetch_company_with_retries(self, cnpj, max_retries=3, initial_wait=2):
        """
        Tenta buscar a empresa pelo CNPJ várias vezes, com espera incremental.
        
        Args:
            cnpj (str): CNPJ da empresa
            max_retries (int): Número máximo de tentativas
            initial_wait (int): Tempo de espera inicial em segundos
            
        Returns:
            dict: Dados da empresa ou None se não encontrada
        """
        wait_time = initial_wait
        
        for attempt in range(max_retries):
            # Esperar antes de tentar - a primeira chamada também espera para dar
            # tempo ao sistema remoto processar o registro anterior
            logger.info(f"Aguardando {wait_time}s antes da tentativa {attempt+1} de buscar o CNPJ")
            time.sleep(wait_time)
            
            # Buscar empresa pelo CNPJ
            company = self.get_company_by_cnpj(cnpj)
            
            if company and 'id' in company:
                logger.info(f"Empresa encontrada na tentativa {attempt+1}. ID: {company['id']}")
                return company
                
            # Aumentar tempo de espera para próxima tentativa
            wait_time *= 1.5
            
        logger.warning(f"Empresa não encontrada após {max_retries} tentativas")
        return None

    def get_company_by_cnpj(self, cnpj):
        """
        Busca uma empresa pelo CNPJ.
        """
        if not cnpj:
            logger.warning("CNPJ vazio fornecido para busca")
            return None
            
        endpoint = f"{self.base_url}/receivers?searchField={cnpj}"
        
        logger.info(f"Consultando empresa por CNPJ: {cnpj}")
        
        try:
            response = self.http_client.get(endpoint)
            logger.debug(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Verificar se retornou algum resultado
                    if result and isinstance(result, list) and len(result) > 0:
                        logger.info(f"Empresa encontrada com CNPJ {cnpj}: {result[0].get('id')}")
                        return result[0]  # Retorna a primeira empresa encontrada
                    else:
                        logger.info(f"Nenhuma empresa encontrada com o CNPJ: {cnpj}")
                        return None
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar resposta: {response.text}")
                    return None
            
            # Tratamento específico para outros status codes
            if response.status_code == 404:
                logger.info(f"API retornou 404 para CNPJ {cnpj} - empresa não existe")
                return None
                
            logger.warning(f"API retornou status inesperado: {response.status_code} para CNPJ {cnpj}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar empresa por CNPJ: {str(e)}")
            return None