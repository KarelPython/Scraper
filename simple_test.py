import requests
import urllib3
from bs4 import BeautifulSoup

# Vypnutí varování o nezabezpečeném SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_download():
    """
    Jednoduchý test stažení stránky z Jobs.cz
    """
    print("=== JEDNODUCHÝ TEST STAŽENÍ STRÁNKY ===")
    
    # URL adresa pro testování
    url = "https://www.jobs.cz/prace/praha/"
    
    print(f"Stahuji stránku: {url}")
    
    try:
        # Přidání náhodného user-agent pro snížení pravděpodobnosti blokování
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'cs,en-US;q=0.7,en;q=0.3'
        }
        
        # Stažení stránky
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        
        print(f"Stránka úspěšně stažena (status: {response.status_code}, velikost: {len(response.text)} znaků)")
        
        # Uložení HTML kódu
        with open('simple_test_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"HTML kód stránky uložen do souboru simple_test_page.html")
        
        # Parsování HTML pomocí BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Hledání nadpisů
        h1_elements = soup.find_all('h1')
        print(f"Nalezeno {len(h1_elements)} elementů h1:")
        for h1 in h1_elements:
            print(f"  - {h1.text.strip()}")
        
        # Hledání odkazů na nabídky práce
        job_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/rpd/' in href or '/pd/' in href or '/fp/' in href:
                if href.startswith('/'):
                    href = 'https://www.jobs.cz' + href
                job_links.append(href)
        
        print(f"Nalezeno {len(job_links)} odkazů na nabídky práce:")
        for i, link in enumerate(job_links[:5]):  # Zobrazíme jen prvních 5 odkazů
            print(f"  {i+1}. {link}")
        
        if len(job_links) > 5:
            print(f"  ... a dalších {len(job_links) - 5} odkazů")
        
        # Uložení odkazů do souboru
        with open('job_links.txt', 'w', encoding='utf-8') as f:
            for link in job_links:
                f.write(f"{link}\n")
        
        print(f"Odkazy na nabídky práce uloženy do souboru job_links.txt")
        
        return True
        
    except Exception as e:
        print(f"Chyba při stahování stránky: {e}")
        return False

if __name__ == "__main__":
    test_download() 