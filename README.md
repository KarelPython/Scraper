# Scraper pracovních nabídek z Jobs.cz

Tento projekt automaticky scrapuje pracovní nabídky z webu Jobs.cz podle zadaných lokalit a klíčového slova "python". Nalezené nabídky jsou ukládány do Google Sheets pro další analýzu.

## Funkce

- Vyhledávání pracovních nabídek podle lokalit a radiusu
- Extrakce detailních informací o nabídkách (název pozice, společnost, plat, popis, lokalita)
- Automatické ukládání do Google Sheets
- Kontrola duplicit pro zamezení opakovaného ukládání stejných nabídek
- Automatické spouštění pomocí GitHub Actions každý den

## Požadavky

- Python 3.13
- Knihovny uvedené v `requirements.txt`
- Přístup ke Google Sheets API (credentials.json)

## Instalace

1. Naklonujte repozitář:
   ```
   git clone https://github.com/vas-uzivatelske-jmeno/jobs-scraper.git
   cd jobs-scraper
   ```

2. Nainstalujte závislosti:
   ```
   pip install -r requirements.txt
   ```

3. Vytvořte projekt v Google Cloud Console a povolte Google Sheets API
4. Stáhněte credentials.json pro přístup k API

## Konfigurace

1. Nastavte proměnné prostředí:
   - `SPREADSHEET_ID` - ID Google Sheets dokumentu pro ukládání dat

2. Upravte lokality v souboru `jobs-scraper_komentare.py`:
   ```python
   locations = [
       ("plzen", 20),  # Plzeň s radiusem 20 km
       ("praha", 10)   # Praha s radiusem 10 km
   ]
   ```

## Použití

Spusťte scraper příkazem:
```
python jobs-scraper_komentare.py
```

## GitHub Actions

Projekt obsahuje workflow pro automatické spouštění scraperu každý den. Pro nastavení:

1. V repozitáři nastavte tajné proměnné (Settings > Secrets):
   - `GOOGLE_CREDENTIALS` - obsah souboru credentials.json
   - `SPREADSHEET_ID` - ID Google Sheets dokumentu

2. Workflow se spustí automaticky podle nastaveného rozvrhu nebo ho můžete spustit manuálně v záložce Actions.

## Struktura projektu

- `jobs-scraper_komentare.py` - hlavní skript pro scrapování
- `main.yml` - konfigurační soubor pro GitHub Actions
- `requirements.txt` - seznam závislostí
- `scraper.log` - log soubor s informacemi o průběhu scrapování

## Licence

Tento projekt je licencován pod MIT licencí.
