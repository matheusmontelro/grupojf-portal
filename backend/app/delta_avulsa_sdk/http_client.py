"""Cliente HTTP para comunicação com API Delta"""
import httpx
import logging
from typing import Dict, Optional, Any
import json

logger = logging.getLogger(__name__)

class DeltaHttpClient:
    """Cliente HTTP com suporte a redirecionamento automático e retry"""
    
    def __init__(self, base_url: str, headers: Dict[str, str], timeout: int = 30):
        self.base_url = base_url
        self.headers = headers
        self.timeout = timeout
        # Desabilita redirecionamento automático para capturar headers do 201
        self.client = httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout)
        )
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
        
    def _log_request(self, method: str, url: str, **kwargs):
        """Log detalhado da requisição"""
        logger.debug(f"Request: {method} {url}")
        if 'json' in kwargs:
            logger.debug(f"Body: {json.dumps(kwargs['json'], indent=2)}")
            
    def _log_response(self, response: httpx.Response):
        """Log detalhado da resposta"""
        logger.debug(f"Response Status: {response.status_code}")
        logger.debug(f"Response Headers: {dict(response.headers)}")
        try:
            logger.debug(f"Response Body: {json.dumps(response.json(), indent=2)}")
        except:
            logger.debug(f"Response Body: {response.text}")
            
    def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Executa requisição HTTP"""
        url = f"{self.base_url}{endpoint}"
        
        # Adiciona headers padrão
        if 'headers' in kwargs:
            kwargs['headers'].update(self.headers)
        else:
            kwargs['headers'] = self.headers
            
        self._log_request(method, url, **kwargs)
        
        try:
            response = self.client.request(method, url, **kwargs)
            self._log_response(response)
            
            # Para status 201, não faz raise_for_status para preservar headers
            if response.status_code == 201:
                return response
            
            # Se houver redirecionamento (3xx), seguir manualmente se necessário
            if 300 <= response.status_code < 400 and 'Location' in response.headers:
                # Log do redirecionamento mas não segue automaticamente
                logger.info(f"Redirect detected: {response.headers['Location']}")
                return response
                
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error: {e}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
            
    def get(self, endpoint: str, params: Optional[Dict] = None) -> httpx.Response:
        """GET request"""
        return self.request("GET", endpoint, params=params)
        
    def post(self, endpoint: str, json: Optional[Dict] = None) -> httpx.Response:
        """POST request"""
        return self.request("POST", endpoint, json=json)
        
    def put(self, endpoint: str, json: Optional[Dict] = None) -> httpx.Response:
        """PUT request"""
        return self.request("PUT", endpoint, json=json)
        
    def delete(self, endpoint: str) -> httpx.Response:
        """DELETE request"""
        return self.request("DELETE", endpoint)
        
    def patch(self, endpoint: str, json: Optional[Dict] = None) -> httpx.Response:
        """PATCH request"""
        return self.request("PATCH", endpoint, json=json)