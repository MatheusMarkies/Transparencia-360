import httpx
import asyncio

async def debug_api():
    deputy_id = 160569
    year = 2025
    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{deputy_id}/despesas?ano={year}&ordem=ASC&ordenarPor=ano"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json().get('dados', [])
        if data:
            print("Keys in first expense record:")
            print(data[0].keys())
            print("\nFirst record sample:")
            print(data[0])
        else:
            print("No data found.")

if __name__ == "__main__":
    asyncio.run(debug_api())
