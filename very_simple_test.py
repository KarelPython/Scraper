import requests
import sys
import time
import os

def test_download():
    """
    Velmi jednoduchý test stažení stránky s nabídkou práce z Jobs.cz
    """
    print("=== VELMI JEDNODUCHÝ TEST STAŽENÍ STRÁNKY ===")
    
    # URL adresy pro testování
    urls = [
        "https://www.jobs.cz/",  # Hlavní stránka
        "https://www.jobs.cz/prace/praha/",  # Výpis nabídek pro Prahu
        "https://www.jobs.cz/pd/1694307246/",  # Konkrétní nabídka práce
        "https://www.jobs.cz/rpd/1694307246/"  # Alternativní URL pro stejnou nabídku
    ]
    
    for i, url in enumerate(urls):
        print(f"\nTest {i+1}/{len(urls)}: Stahuji stránku: {url}")
        
        try:
            # Přidání náhodného user-agent pro snížení pravděpodobnosti blokování
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'cs,en-US;q=0.7,en;q=0.3',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            # Stažení stránky
            print(f"Odesílám HTTP požadavek...")
            response = requests.get(url, headers=headers, timeout=30, verify=False)
            
            print(f"Stránka úspěšně stažena (status: {response.status_code}, velikost: {len(response.text)} znaků)")
            
            # Uložení HTML kódu
            filename = f"test_{i+1}_{url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            print(f"HTML kód stránky uložen do souboru {filename}")
            
            # Krátká pauza mezi požadavky
            if i < len(urls) - 1:
                print("Čekám 5 sekund před dalším požadavkem...")
                time.sleep(5)
            
        except Exception as e:
            print(f"Chyba při stahování stránky: {e}")
            print(f"Typ chyby: {type(e)}")
            print(f"Detaily chyby: {str(e)}")
    
    return True

if __name__ == "__main__":
    print(f"Python verze: {sys.version}")
    print(f"Requests verze: {requests.__version__}")
    
    # Přímý výpis do konzole
    import sys
    sys.stdout.flush()
    
    # Spuštění testu
    test_download()
    
    # Výpis seznamu vytvořených souborů
    print("\nSeznam vytvořených souborů:")
    for file in os.listdir('.'):
        if file.startswith('test_') and file.endswith('.html'):
            print(f" - {file} ({os.path.getsize(file)} bajtů)") 