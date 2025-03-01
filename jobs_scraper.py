import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import logging
import json
import sys
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Získání absolutní cesty k adresáři, kde se nachází tento skript
script_dir = os.path.dirname(os.path.abspath(__file__))
# Nastavení pracovního adresáře na adresář skriptu
os.chdir(script_dir)

# Kontrola, zda jsme v testovacím režimu
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

# Nastavení logování pro sledování průběhu scrapování a případných chyb
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(script_dir, 'scraper.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logging.info(f"Skript spuštěn z adresáře: {os.getcwd()}")
logging.info(f"Adresář skriptu: {script_dir}")
logging.info(f"Testovací režim: {'ZAPNUTÝ' if TEST_MODE else 'VYPNUTÝ'}")

# Ověření existence a platnosti JSON souboru s credentials
try:
    # Zkusíme najít credentials.json v různých umístěních
    possible_paths = [
        'credentials.json',
        '../credentials.json',
        os.path.join(script_dir, 'credentials.json'),
        os.path.join(os.path.dirname(script_dir), 'credentials.json')
    ]
    
    credentials_path = None
    for path in possible_paths:
        if os.path.exists(path):
            credentials_path = path
            logging.info(f"Credentials file found at: {path}")
            break
    
    if not credentials_path and not TEST_MODE:
        logging.error("Credentials file not found in any of the expected locations")
        sys.exit(1)
    elif not credentials_path and TEST_MODE:
        logging.warning("Credentials file not found, but continuing in TEST_MODE")
    
    # Pokus o načtení a opravu JSON souboru
    if credentials_path:
        with open(credentials_path, 'r') as f:
            credentials_content = f.read().strip()
        
        # Pokus o parsování JSON
        try:
            creds_json = json.loads(credentials_content)
            logging.info(f"Credentials file is valid JSON")
            
            # Kontrola základních polí v credentials
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            missing_fields = [field for field in required_fields if field not in creds_json]
            
            if missing_fields and not TEST_MODE:
                logging.error(f"Credentials file is missing required fields: {', '.join(missing_fields)}")
                sys.exit(1)
            elif missing_fields and TEST_MODE:
                logging.warning(f"Credentials file is missing required fields: {', '.join(missing_fields)}, but continuing in TEST_MODE")
            
            # Výpis základních informací o credentials (bez citlivých údajů)
            logging.info(f"Service account type: {creds_json.get('type', 'unknown')}")
            logging.info(f"Project ID: {creds_json.get('project_id', 'unknown')}")
            logging.info(f"Client email: {creds_json.get('client_email', 'unknown')}")
            
        except json.JSONDecodeError as e:
            logging.error(f"Invalid credentials file: {e}")
            if not TEST_MODE:
                logging.info("Attempting to fix common JSON formatting issues...")
                
                # Pokus o opravu běžných problémů s JSON formátem
                if credentials_content.startswith("'") and credentials_content.endswith("'"):
                    credentials_content = credentials_content[1:-1]
                
                # Pokus o parsování opraveného JSON
                try:
                    creds_json = json.loads(credentials_content)
                    # Uložení opraveného JSON
                    with open(credentials_path, 'w') as f:
                        f.write(credentials_content)
                    logging.info("Successfully fixed JSON format issues")
                except json.JSONDecodeError:
                    logging.error("Could not fix JSON format issues")
                    sys.exit(1)
            else:
                logging.warning("Invalid credentials file, but continuing in TEST_MODE")
        
except Exception as e:
    logging.error(f"Error processing credentials file: {e}")
    if not TEST_MODE:
        sys.exit(1)
    else:
        logging.warning("Continuing in TEST_MODE despite credentials error")

class JobsScraper:
    def __init__(self, locations_with_radius):
        """
        # Inicializace scraperu s následujícími parametry:
        # locations_with_radius: seznam dvojic (lokalita, radius)
        # Nastavení přístupu ke Google Docs API
        # Parametry:
        #   locations_with_radius: list of tuples [(str, int)] - seznam lokalit a jejich radiusů
        """
        self.locations = locations_with_radius
        self.keyword = "python"  # Fixní hledaný výraz
        self.jobs_data = []
        self.test_mode = TEST_MODE
        
        # Nastavení Google Docs API
        self.SCOPES = ['https://www.googleapis.com/auth/documents']
        self.DOCUMENT_ID = os.getenv('DOCUMENT_ID')
        
        if not self.DOCUMENT_ID and not self.test_mode:
            logging.error("DOCUMENT_ID environment variable is not set")
            sys.exit(1)
        elif not self.DOCUMENT_ID and self.test_mode:
            logging.warning("DOCUMENT_ID environment variable is not set, but continuing in TEST_MODE")
            self.DOCUMENT_ID = "test_document_id"
            
        if not self.test_mode:
            try:
                logging.info("Initializing Google Docs API connection...")
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_path, scopes=self.SCOPES)
                
                # Výpis informací o credentials pro diagnostiku
                logging.info(f"Service account email: {self.credentials.service_account_email}")
                logging.info(f"Token URI: {self.credentials._token_uri}")
                
                self.service = build('docs', 'v1', credentials=self.credentials)
                
                # Test připojení k API
                logging.info(f"Testing connection to Google Docs API with document ID: {self.DOCUMENT_ID}")
                self.service.documents().get(documentId=self.DOCUMENT_ID).execute()
                logging.info("Successfully connected to Google Docs API")
            except Exception as e:
                logging.error(f"Failed to initialize Google Docs API: {e}")
                
                # Pokud je chyba související s oprávněními, poskytneme další informace
                if "invalid_grant" in str(e):
                    logging.error("This error typically occurs when:")
                    logging.error("1. Service account credentials are invalid or expired")
                    logging.error("2. The service account doesn't exist or was deleted")
                    logging.error("3. The Google Docs document doesn't exist")
                    logging.error("4. The service account doesn't have permission to access the document")
                    
                    logging.error("\nŘešení:")
                    logging.error("1. Zkontrolujte, zda je service account aktivní v Google Cloud Console")
                    logging.error("2. Ujistěte se, že jste sdíleli Google Docs dokument s emailem service accountu")
                    logging.error("3. Zkontrolujte, zda je ID dokumentu správné")
                    logging.error("4. Vygenerujte nové credentials pro service account")
                
                sys.exit(1)
        else:
            logging.info("Skipping Google Docs API initialization in TEST_MODE")
            self.service = None

    def get_existing_jobs(self):
        """
        # Načte existující nabídky z Google Docs pro kontrolu duplicit
        # Vrací seznam URL adres již existujících nabídek
        # Returns:
        #   list[str]: seznam URL adres existujících nabídek
        # Raises:
        #   HttpError: při problému s připojením ke Google Docs
        """
        if self.test_mode:
            logging.info("Skipping loading existing jobs in TEST_MODE")
            return []
            
        try:
            document = self.service.documents().get(documentId=self.DOCUMENT_ID).execute()
            content = document.get('body').get('content')
            
            # Extrahujeme URL adresy z dokumentu
            existing_urls = []
            for element in content:
                if 'paragraph' in element:
                    for paragraph_element in element['paragraph']['elements']:
                        if 'textRun' in paragraph_element:
                            text = paragraph_element['textRun']['content']
                            # Hledáme URL adresy v textu
                            if 'https://www.jobs.cz' in text:
                                # Jednoduchá extrakce URL - v reálném případě by bylo lepší použít regex
                                url_start = text.find('https://www.jobs.cz')
                                url_end = text.find(' ', url_start)
                                if url_end == -1:
                                    url_end = len(text)
                                url = text[url_start:url_end].strip()
                                existing_urls.append(url)
            
            return existing_urls
        except HttpError as err:
            logging.error(f"Chyba při načítání existujících nabídek: {err}")
            return []

    def parse_job_listing(self, job_element):
        """
        # Extrahuje základní informace o pracovní nabídce z HTML elementu
        # Parametry:
        #   job_element: BeautifulSoup element obsahující informace o nabídce
        # Returns:
        #   tuple(str, str): (název pozice, URL nabídky)
        # Raises:
        #   AttributeError: při nesprávné struktuře HTML
        """
        try:
            title = job_element.text.strip()
            link_element = job_element.find('a')
            link = link_element['href'] if link_element else None
            
            if not link:
                return None, None
                
            # Zajistíme, že URL začíná správně
            if not link.startswith('http'):
                link = 'https://www.jobs.cz' + link
                
            # Odstranění parametrů z URL pro konzistentní porovnávání
            # Například: https://www.jobs.cz/pd/123456?param=value -> https://www.jobs.cz/pd/123456
            if '?' in link:
                link = link.split('?')[0]
                
            # Odstranění koncového lomítka pro konzistentní porovnávání
            if link.endswith('/'):
                link = link[:-1]
                
            logging.debug(f"Zpracována nabídka: {title} s URL: {link}")
            return title, link
        except Exception as e:
            logging.error(f"Chyba při parsování nabídky: {e}")
            return None, None

    def get_job_details(self, url):
        """
        # Získá detailní informace o pracovní nabídce z její stránky
        # Stahuje informace o společnosti, platu a popisu pozice
        # Parametry:
        #   url: str - URL adresa nabídky
        # Returns:
        #   dict: slovník s detaily nabídky nebo None při chybě
        # Raises:
        #   RequestException: při problému se stažením stránky
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extrakce informací o společnosti
            company = soup.find('div', class_="IconWithText")
            company_name = company.find('p', class_="typography-body-medium-text-regular").text.strip() if company else "Neuvedeno"

            # Extrakce informací o platu
            salary_element = soup.find("div", {"data-test": "jd-salary"})
            salary = salary_element.find("p", class_="typography-body-medium-text-regular").text.strip() if salary_element else "Neuvedeno"

            # Extrakce popisu pozice
            description_element = soup.find("div", {"data-test": "jd-body-richtext"})
            description = description_element.text.strip() if description_element else "Neuvedeno"

            # Extrakce lokality
            location_element = soup.find("div", {"data-test": "jd-workplace"})
            location = location_element.text.strip() if location_element else "Neuvedeno"

            return {
                "company": company_name,
                "salary": salary,
                "description": description,
                "location": location
            }
        except Exception as e:
            logging.error(f"Chyba při získávání detailů nabídky: {e}")
            return None

    def append_to_docs(self, new_jobs):
        """
        # Přidá nové nabídky do Google Docs
        # Formátuje data a přidává časové razítko
        # Parametry:
        #   new_jobs: list[dict] - seznam nových pracovních nabídek
        # Raises:
        #   HttpError: při problému s připojením ke Google Docs
        """
        if self.test_mode:
            logging.info(f"TEST_MODE: Would add {len(new_jobs)} jobs to Google Docs")
            for job in new_jobs:
                logging.info(f"TEST_MODE: Job: {job['title']} at {job['company']}")
            return
            
        try:
            # Získáme aktuální dokument
            document = self.service.documents().get(documentId=self.DOCUMENT_ID).execute()
            
            # Připravíme obsah pro přidání
            requests = []
            
            # Přidáme nadpis s datem
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            requests.append({
                'insertText': {
                    'location': {
                        'index': document['body']['content'][-1]['endIndex'] - 1
                    },
                    'text': f"\n\nNové nabídky nalezené {current_date}:\n"
                }
            })
            
            # Přidáme formátování nadpisu
            end_index = document['body']['content'][-1]['endIndex'] - 1 + len(f"\n\nNové nabídky nalezené {current_date}:\n")
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': document['body']['content'][-1]['endIndex'] - 1,
                        'endIndex': end_index
                    },
                    'textStyle': {
                        'bold': True,
                        'fontSize': {
                            'magnitude': 14,
                            'unit': 'PT'
                        }
                    },
                    'fields': 'bold,fontSize'
                }
            })
            
            # Přidáme jednotlivé nabídky
            for job in new_jobs:
                job_text = (
                    f"Pozice: {job['title']}\n"
                    f"Společnost: {job['company']}\n"
                    f"Lokalita: {job['location']}\n"
                    f"Plat: {job['salary']}\n"
                    f"URL: {job['link']}\n"
                    f"Popis: {job['description']}\n\n"
                    f"-------------------------------------------\n\n"
                )
                
                requests.append({
                    'insertText': {
                        'location': {
                            'index': end_index
                        },
                        'text': job_text
                    }
                })
                
                end_index += len(job_text)
            
            # Provedeme aktualizaci dokumentu
            self.service.documents().batchUpdate(
                documentId=self.DOCUMENT_ID,
                body={'requests': requests}
            ).execute()
            
            logging.info(f"Přidáno {len(new_jobs)} nových nabídek do Google Docs")
        except HttpError as err:
            logging.error(f"Chyba při ukládání do Google Docs: {err}")

    def scrape_jobs(self):
        """
        # Hlavní metoda pro scrapování nabídek
        # Prochází všechny lokality a stránky s výsledky
        # Kontroluje duplicity a ukládá pouze nové nabídky
        # Returns:
        #   list[dict]: seznam nových pracovních nabídek
        """
        existing_jobs = self.get_existing_jobs()
        new_jobs = []
        
        # Pomocný set pro sledování již zpracovaných URL v rámci aktuálního běhu
        processed_urls = set(existing_jobs)

        # Procházení všech zadaných lokalit
        for location, radius in self.locations:
            page = 1
            consecutive_empty_pages = 0
            max_empty_pages = 3  # Pokud 3 stránky po sobě nemají nové nabídky, ukončíme procházení
            
            while True:
                try:
                    # Sestavení URL pro aktuální stránku a lokalitu
                    url = f"https://www.jobs.cz/prace/{location}/?q[]={self.keyword}&locality[radius]={radius}"
                    if page > 1:
                        url += f"&page={page}"

                    logging.info(f"Stahuji nabídky pro lokalitu {location}, stránka {page}")
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')

                    jobs = soup.find_all('h2', class_="SearchResultCard__title")
                    
                    # Kontrola, zda stránka obsahuje nabídky
                    if not jobs:
                        logging.info(f"Žádné nabídky na stránce {page} pro lokalitu {location}")
                        break
                    
                    # Počítadlo nových nabídek na této stránce
                    new_jobs_on_page = 0
                    
                    # Výpis počtu nalezených nabídek na stránce
                    logging.info(f"Nalezeno {len(jobs)} nabídek na stránce {page}")

                    for job in jobs:
                        title, link = self.parse_job_listing(job)
                        if not title or not link:
                            continue

                        # Kontrola duplicit - jak proti existujícím nabídkám, tak proti již zpracovaným v tomto běhu
                        if link not in processed_urls:
                            processed_urls.add(link)  # Přidáme do zpracovaných URL
                            details = self.get_job_details(link)
                            if details:
                                job_data = {
                                    'title': title,
                                    'link': link,
                                    **details
                                }
                                new_jobs.append(job_data)
                                new_jobs_on_page += 1
                                logging.info(f"Nalezena nová nabídka: {title} v {location}")
                                time.sleep(1)  # Prodleva mezi požadavky
                        else:
                            logging.info(f"Přeskakuji duplicitní nabídku: {title}")
                    
                    # Kontrola, zda jsme našli nějaké nové nabídky na této stránce
                    if new_jobs_on_page == 0:
                        consecutive_empty_pages += 1
                        logging.info(f"Žádné nové nabídky na stránce {page}, počet prázdných stránek po sobě: {consecutive_empty_pages}")
                        if consecutive_empty_pages >= max_empty_pages:
                            logging.info(f"Ukončuji procházení pro lokalitu {location} - {max_empty_pages} prázdných stránek po sobě")
                            break
                    else:
                        consecutive_empty_pages = 0  # Resetujeme počítadlo, pokud jsme našli nějaké nové nabídky
                        logging.info(f"Nalezeno {new_jobs_on_page} nových nabídek na stránce {page}")

                    page += 1
                    time.sleep(2)  # Prodleva mezi stránkami

                    # V testovacím režimu omezíme počet stránek
                    if self.test_mode and page > 1:
                        logging.info("TEST_MODE: Omezení na 1 stránku výsledků")
                        break
                    
                    # Omezení maximálního počtu stránek (pro případ, že by web vracel nekonečně mnoho stránek)
                    if page > 50:
                        logging.warning(f"Dosažen maximální počet stránek (50) pro lokalitu {location}")
                        break

                except Exception as e:
                    logging.error(f"Chyba při scrapování stránky {page} pro lokalitu {location}: {e}")
                    break

        # Výpis souhrnných informací
        logging.info(f"Celkem nalezeno {len(new_jobs)} nových nabídek")
        
        if new_jobs:
            self.append_to_docs(new_jobs)
        return new_jobs

def main():
    """
    # Hlavní funkce programu
    # Definuje lokality pro vyhledávání a spouští scraping
    """
    # Definice lokalit a jejich radiusů
    locations = [
        ("plzen", 20),  # Plzeň s radiusem 20 km
        ("praha", 10)   # Praha s radiusem 10 km
    ]
    
    scraper = JobsScraper(locations)
    scraper.scrape_jobs()

if __name__ == "__main__":
    main() 