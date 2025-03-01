# Scraper pracovních nabídek z Jobs.cz

Tento projekt automaticky scrapuje pracovní nabídky z webu Jobs.cz podle zadaných lokalit a klíčového slova "python". Nalezené nabídky jsou ukládány do Google Docs pro další analýzu.

## Funkce

- Vyhledávání pracovních nabídek podle lokalit a radiusu
- Extrakce detailních informací o nabídkách (název pozice, společnost, plat, popis, lokalita)
- Extrakce rozšířených informací (benefity, požadavky, informace o společnosti, typ úvazku, vzdělání, jazyky)
- Automatické ukládání do Google Docs s formátováním
- Kontrola duplicit pro zamezení opakovaného ukládání stejných nabídek
- Automatické spouštění pomocí GitHub Actions každý den
- Odolnost vůči SSL chybám a výpadkům připojení
- Automatické zálohování dat do lokálního JSON souboru

## Požadavky

- Python 3.13
- Knihovny uvedené v `requirements.txt` (včetně backoff pro opakování operací)
- Přístup ke Google Docs API (credentials.json)

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

3. Vytvořte projekt v Google Cloud Console a povolte Google Docs API
4. Stáhněte credentials.json pro přístup k API

## Konfigurace

1. Nastavte proměnné prostředí:
   - `DOCUMENT_ID` - ID Google Docs dokumentu pro ukládání dat
   - `TEST_MODE` - nastavte na "true" pro testovací režim bez ukládání do Google Docs

2. Upravte lokality v souboru `jobs_scraper.py`:
   ```python
   locations = [
       ("plzen", 20),  # Plzeň s radiusem 20 km
       ("praha", 10)   # Praha s radiusem 10 km
   ]
   ```

## Použití

Spusťte scraper příkazem:
```
python jobs_scraper.py
```

## Zpracování chyb a odolnost

Scraper obsahuje několik mechanismů pro zvýšení odolnosti:

- Automatické opakování operací při selhání (pomocí knihovny backoff)
- Alternativní metody pro přidávání obsahu do Google Docs
- Rozdělení velkých požadavků na menší části pro překonání limitů API
- Automatické zálohování dat do lokálního souboru
- Podrobné logování pro snadnější diagnostiku problémů

## GitHub Actions

Projekt obsahuje workflow pro automatické spouštění scraperu každý den. Pro nastavení:

1. V repozitáři nastavte tajné proměnné (Settings > Secrets):
   - `GOOGLE_CREDENTIALS` - obsah souboru credentials.json
   - `DOCUMENT_ID` - ID Google Docs dokumentu

2. Workflow se spustí automaticky podle nastaveného rozvrhu nebo ho můžete spustit manuálně v záložce Actions.

## Struktura projektu

- `jobs_scraper.py` - hlavní skript pro scrapování
- `main.yml` - konfigurační soubor pro GitHub Actions
- `requirements.txt` - seznam závislostí
- `scraper.log` - log soubor s informacemi o průběhu scrapování
- `jobs_backup.json` - záložní soubor s nalezenými nabídkami

## Licence

Tento projekt je licencován pod MIT licencí.
