import httpx
import os
import asyncio
import aiofiles  # Nova importação para I/O assíncrono
from pathlib import Path

# Dynamic Pathing relative to worker src structure
WORKER_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = WORKER_ROOT / "data" / "downloads" / "notas_fiscais"

class CamaraExtractor:
    def __init__(self):
        self.base_url = "https://dadosabertos.camara.leg.br/api/v2/deputados"
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

    async def get_expenses(self, deputy_id: int, year: int = 2025):
        url = f"{self.base_url}/{deputy_id}/despesas?ano={year}&ordem=ASC&ordenarPor=ano"
        client = self.get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json().get('dados', [])
        return [d for d in data if d.get('urlDocumento')]

    async def download_pdf(self, url: str, filename: str):
        target_path = DATA_DIR / filename
        if target_path.exists():
            return str(target_path)
            
        client = self.get_client()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                # OTIMIZAÇÃO: Escrita de arquivo não-bloqueante usando aiofiles
                async with aiofiles.open(target_path, "wb") as f:
                    await f.write(resp.content)
                return str(target_path)
        except Exception as e:
            print(f"Error downloading {url}: {e}")
        return None

    async def process_deputy(self, deputy_id: int):
        expenses = await self.get_expenses(deputy_id)
        results = []
        
        # Limit to 3 in production for stability
        # Dica de Engenharia: Se for aumentar esse limite futuramente, 
        # considere usar um asyncio.Semaphore() aqui ou no download_pdf
        # para não abrir centenas de conexões simultâneas com a API da Câmara.
        for exp in expenses[:3]: 
            doc_url = exp['urlDocumento']
            filename = f"dep_{deputy_id}_{exp['codDocumento']}.pdf"
            local_path = await self.download_pdf(doc_url, filename)
            
            if local_path:
                results.append({
                    "alerta": "DESPESA_FISCAL",
                    "prova_documental": {
                        "texto_extraido": exp['tipoDespesa'],
                        "arquivo_local": local_path,
                        "onde_esta_essa_info_url": doc_url
                    },
                    "metadados": {
                        "fornecedor": exp['nomeFornecedor'],
                        "cnpj": exp['cnpjCpfFornecedor'],
                        "valor": exp['valorDocumento'],
                        "data": exp['dataDocumento']
                    }
                })
        return results

if __name__ == "__main__":
    extractor = CamaraExtractor()
    try:
        # Arthur Lira id is 160569
        asyncio.run(extractor.process_deputy(160569))
    finally:
        asyncio.run(extractor.close())