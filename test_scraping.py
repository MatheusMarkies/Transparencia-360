import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def fetch_deputy_page(session, url):
    # Usando User-Agent real
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    async with session.get(url, headers=headers) as response:
        return await response.text()

async def main():
    url = "https://www.camara.leg.br/deputados/204554/pessoal-gabinete"
    async with aiohttp.ClientSession() as session:
        html = await fetch_deputy_page(session, url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # O HTML da Câmara renderiza pelo Angular/React ou é SSR?
        title = soup.find('title')
        print(f"Page Title: {title.text if title else 'No Title'}")
        
        # Vamos tentar achar todos as tabelas ou divs relevantes
        tables = soup.find_all('table')
        if not tables:
            print("No simple tables, it might be dynamically rendered.")
            
        print("Looking for staff keywords:")
        gabinete_section = soup.body.text if soup.body else ""
        if "Secretário Parlamentar" in gabinete_section:
            print("Found Secretário Parlamentar text!")
            
        with open("page_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved HTML to page_dump.html")

if __name__ == "__main__":
    asyncio.run(main())
