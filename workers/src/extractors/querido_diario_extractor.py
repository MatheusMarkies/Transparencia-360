import httpx
import os
import asyncio
from pathlib import Path

# Dynamic Pathing relative to worker src structure
WORKER_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = WORKER_ROOT / "data" / "downloads" / "diarios_oficiais"

class QueridoDiarioExtractor:
    def __init__(self):
        self.api_url = "https://api.queridodiario.ok.org.br/api/gazettes"
        self._client = None
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def get_client(self):
        """Reusable client for performance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
        return self._client

    async def close(self):
        """Clean up resources."""
        if self._client:
            await self._client.aclose()

    async def search_gazettes(self, keyword: str):
        params = {"querystring": keyword}
        client = self.get_client()
        resp = await client.get(self.api_url, params=params)
        resp.raise_for_status()
        return resp.json().get('gazettes', [])

    async def download_gazette(self, url: str, gazette_id: str):
        target_path = DATA_DIR / f"gazette_{gazette_id}.pdf"
        if target_path.exists():
             return str(target_path)

        client = self.get_client()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return str(target_path)
        except Exception as e:
            print(f"Error downloading gazette {gazette_id}: {e}")
        return None

    async def process_cnpj(self, cnpj: str):
        gazettes = await self.search_gazettes(cnpj)
        results = []
        for g in gazettes[:2]: # Limit to 2 for stability
            doc_url = g['url']
            local_path = await self.download_gazette(doc_url, g['file_checksum'])
            if local_path:
                results.append({
                    "alerta": "DIARIO_OFICIAL",
                    "prova_documental": {
                        "texto_extraido": f"Publicação no Diário de {g['territory_name']}",
                        "arquivo_local": local_path,
                        "onde_esta_essa_info_url": doc_url
                    },
                    "metadados": {
                        "cnpj_buscado": cnpj,
                        "data": g['date'],
                        "entidade": g['territory_name']
                    }
                })
        return results

if __name__ == "__main__":
    extractor = QueridoDiarioExtractor()
    try:
        # Mock CNPJ for testing
        asyncio.run(extractor.process_cnpj("00.000.000/0001-00"))
    finally:
        asyncio.run(extractor.close())
