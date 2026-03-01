import asyncio
import aiohttp
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CamaraCabinetScraper:
    def __init__(self, request_delay: float = 0.5):
        self.base_url = "https://www.camara.leg.br/deputados"
        self.request_delay = request_delay

    async def fetch_cabinet_staff(self, deputy_id: int) -> list:
        """
        Scrapes the list of parliamentary secretaries and CNEs for a deputy.
        URL: https://www.camara.leg.br/deputados/{id}/gabinete
        """
        url = f"{self.base_url}/{deputy_id}/gabinete"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            async with aiohttp.ClientSession() as session:
                await asyncio.sleep(self.request_delay)
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch cabinet for deputy {deputy_id}: HTTP {response.status}")
                        return []
                    
                    html = await response.text()
                    return self._parse_cabinet_html(html)
        except Exception as e:
            logger.error(f"Error scraping cabinet for {deputy_id}: {e}")
            return []

    def _parse_cabinet_html(self, html: str) -> list:
        """
        Parses the personnel tables from the cabinet page.
        """
        soup = BeautifulSoup(html, 'html.parser')
        staff_list = []
        
        # The page usually has sections like "Secretários Parlamentares" and "CNE"
        # We look for tables or list items containing staff names
        tables = soup.find_all('table', class_='gabinete-pessoal__lista')
        
        for table in tables:
            rows = table.find_all('tr')[1:] # Skip header
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    name = cols[0].get_text(strip=True)
                    role = cols[1].get_text(strip=True)
                    # We often don't have the office location directly in the table, 
                    # but usually it's Brasília - DF for these types of roles.
                    staff_list.append({
                        "nome": name,
                        "cargo": role,
                        "lotacao": "Brasília - DF" # Default for parliamentary secretaries
                    })
        
        # Fallback for different HTML structures if any
        if not staff_list:
            # Look for list-based structures
            items = soup.find_all('li', class_='gabinete-pessoal__item')
            for item in items:
                name_tag = item.find('span', class_='gabinete-pessoal__nome')
                role_tag = item.find('span', class_='gabinete-pessoal__cargo')
                if name_tag:
                    staff_list.append({
                        "nome": name_tag.get_text(strip=True),
                        "cargo": role_tag.get_text(strip=True) if role_tag else "Assessor",
                        "lotacao": "Brasília - DF"
                    })

        logger.info(f"  Parsed {len(staff_list)} staff members from HTML")
        return staff_list

async def test():
    scraper = CamaraCabinetScraper()
    # Test with Abílio Santana (id 204554)
    staff = await scraper.fetch_cabinet_staff(204554)
    for s in staff[:5]:
        print(f"  - {s['nome']} ({s['cargo']})")

if __name__ == "__main__":
    asyncio.run(test())
