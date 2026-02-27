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
    
    def _post(self, endpoint: str, data: Dict[str, Any], retries: int = 3) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        for attempt in range(retries):
            try:
                response = requests.post(url, json=data, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.warning(f"Failed to post data to {url} (Attempt {attempt+1}/{retries}): {e}")
                time.sleep(2 ** attempt)
        logger.error(f"Max retries reached. Could not sync to {endpoint}.")
        return None

    def ingest_politician(self, politician: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post("politician", politician)
    
    def ingest_promise(self, external_id: str, promise: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/promise", promise)
    
    def ingest_vote(self, external_id: str, vote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._post(f"politician/{external_id}/vote", vote)

class GovAPIClient:
    """Base class for handling generic GET requests to Government APIs with rate limiting"""
    def __init__(self, base_url: str, request_delay: float = 1.0):
        self.base_url = base_url
        self.request_delay = request_delay
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}/{endpoint}"
        try:
            time.sleep(self.request_delay) # basic rate limit handling
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            return None
