import os
import requests
import time
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackendClient:
    def __init__(self, base_url: str = "http://localhost:8080/api/internal/workers/ingest"):
        self.base_url = base_url
    
    def _post(self, endpoint: str, data: Dict[str, Any], retries: int = 5) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        for attempt in range(retries):
            try:
                response = requests.post(url, json=data, timeout=15)
                # If we get local/database issues (500), we should definitely retry
                if response.status_code >= 500:
                    logger.warning(f"  ⚠️ Server error (500) at {endpoint}. Possible lock contention. Retrying...")
                    time.sleep(1 + (2 ** attempt)) # Exponential backoff
                    continue
                
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.warning(f"Failed to post to {url} (Attempt {attempt+1}/{retries}): {e}")
                time.sleep(1 + (2 ** attempt))
        logger.error(f"Max retries reached. Could not sync to {endpoint}.")
        return None

    def ingest_politician(self, politician: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post("politician", politician)
    
    def ingest_promise(self, external_id: str, promise: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/promise", promise)
    
    def ingest_vote(self, external_id: str, vote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/vote", vote)

    def ingest_sessao(self, external_id: str, sessao: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/sessao", sessao)

    def ingest_despesa(self, external_id: str, despesa: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/despesa", despesa)

    def ingest_emenda_pix(self, external_id: str, municipio_ibge: str, emenda: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/emenda_pix/{municipio_ibge}", emenda)

    def ingest_contrato_municipal(self, municipio_ibge: str, empresa_cnpj: str, empresa_name: str) -> Optional[Dict[str, Any]]:
        # Envia os dados via query params (como o Spring Boot @RequestParam espera),
        # mas usa o parâmetro 'params' do requests para fazer o URL encoding seguro automaticamente.
        url = f"{self.base_url}/municipio/{municipio_ibge}/contrato"
        payload = {
            "empresaCnpj": str(empresa_cnpj).strip(),
            "empresaName": str(empresa_name).strip()
        }
        for attempt in range(3):
            try:
                # Usa params=payload para colocar as variáveis na URL de forma segura
                response = requests.post(url, params=payload, timeout=10)
                response.raise_for_status()
                return {"status": "success"}
            except requests.RequestException as e:
                logger.warning(f"Failed to post data to {url} (Attempt {attempt+1}/3): {e}")
                time.sleep(2 ** attempt)
        logger.error(f"Max retries reached. Could not sync contrato to {municipio_ibge}.")
        return None

    def ingest_pessoa_societaria(self, pessoa_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post("pessoa/societario", pessoa_data)

class GovAPIClient:
    """Base class for handling generic GET requests to Government APIs with rate limiting"""
    def __init__(self, base_url: str, request_delay: float = 1.0):
        self.base_url = base_url
        self.request_delay = request_delay
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 10) -> Optional[Any]:
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(retries):
            try:
                # Add a small delay between requests even if they succeed
                time.sleep(self.request_delay)
                
                # Increased timeout to 45s for slow gov proxies
                response = requests.get(url, params=params, timeout=45)
                response.raise_for_status()
                return response.json()
                
            except (requests.Timeout, requests.RequestException) as e:
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                
                # For 504 or timeouts, we wait significantly longer
                is_transient = (status_code and status_code in [500, 502, 503, 504]) or isinstance(e, requests.Timeout)
                
                if is_transient and attempt < retries - 1:
                    wait_time = min(30, (2 ** attempt) + (0.1 * attempt)) # Cap backoff at 30s
                    logger.warning(f"  ⚠️ {type(e).__name__} ({status_code or 'Timeout'}) at {url}. "
                                   f"Attempt {attempt+1}/{retries}. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Final failure fetching {url} after {attempt+1} attempts: {e}")
                    return None
        return None

class PortalTransparenciaClient:
    def __init__(self, api_key: str):
        self.base_url = "https://api.portaldatransparencia.gov.br/api-de-dados"
        self.api_key = api_key
        self.headers = {"chave-api-dados": api_key, "Accept": "application/json"}
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 10) -> Optional[Any]:
        if not self.api_key:
            logger.warning("  ⚠️ PORTAL_API_KEY is missing! Skipping call to Portal da Transparência API.")
            return None
            
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(retries):
            try:
                time.sleep(1.0) # Respect rate limits
                # Drop empty params
                current_params = params.copy() if params else {}
                current_params = {k: v for k, v in current_params.items() if v is not None and v != ""}
                
                response = requests.get(url, headers=self.headers, params=current_params, timeout=45)
                
                if response.status_code == 401:
                    logger.warning(f"  ❌ 401 Unauthorized for url: {url}. Please check your PORTAL_API_KEY.")
                    return None
                    
                response.raise_for_status()
                return response.json()
                
            except (requests.Timeout, requests.RequestException) as e:
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                is_transient = (status_code and status_code in [500, 502, 503, 504]) or isinstance(e, requests.Timeout)
                
                if is_transient and attempt < retries - 1:
                    wait_time = min(30, (2 ** attempt) + (0.1 * attempt))
                    logger.warning(f"  ⚠️ {type(e).__name__} ({status_code or 'Timeout'}) at {url}. "
                                   f"Attempt {attempt+1}/{retries}. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Final failure fetching {url} after {attempt+1} attempts: {e}")
                    return None
        return None
