import requests
import sys

print("=== MINIMÁLNÍ TEST STAŽENÍ STRÁNKY ===")
print(f"Python verze: {sys.version}")
print(f"Requests verze: {requests.__version__}")

# URL adresa pro testování
url = "https://www.jobs.cz/"

print(f"Stahuji stránku: {url}")

try:
    # Přidání náhodného user-agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Stažení stránky
    response = requests.get(url, headers=headers, timeout=30, verify=False)
    
    print(f"Stránka úspěšně stažena (status: {response.status_code}, velikost: {len(response.text)} znaků)")
    
    # Uložení HTML kódu
    with open('minimal_test.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    print(f"HTML kód stránky uložen do souboru minimal_test.html")
    
except Exception as e:
    print(f"Chyba při stahování stránky: {e}")
    print(f"Typ chyby: {type(e)}")
    print(f"Detaily chyby: {str(e)}")

print("Test dokončen") 