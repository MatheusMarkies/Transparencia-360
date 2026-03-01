from bs4 import BeautifulSoup
import re

with open('page_dump.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
scripts = soup.find_all('script')

print(f"Total scripts: {len(scripts)}")
for idx, s in enumerate(scripts):
    if s.string and ('window.__INITIAL_STATE__' in s.string or 'funcionarios' in s.string.lower() or 'pessoal' in s.string.lower() or 'api' in s.string.lower()):
        print(f"\n--- Script {idx} ---")
        print(s.string[:500])

links = soup.find_all('a', href=True)
print("API links:")
for l in [l for l in links if 'api' in l['href'].lower()]:
    print("API link:", l['href'])
    
# Let's search inside all text for /api/
pattern = re.compile(r'/api/.*?[\'"]')
matches = pattern.findall(html)
print("\nRegex API matches:", set(matches))
