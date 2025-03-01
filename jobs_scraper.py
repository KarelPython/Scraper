import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import logging
import json
import sys
import os
import ssl
import urllib3
import socket
import backoff
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.api_core.exceptions import RetryError, GoogleAPIError

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

# Potlačení varování o nezabezpečených požadavcích
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Nastavení delšího timeoutu pro socket
socket.setdefaulttimeout(60)  # 60 sekund timeout

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
        
        # Nastavení session pro requests s retry logikou
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,  # Celkový počet pokusů
            backoff_factor=1,  # Faktor pro exponenciální čekání mezi pokusy
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP kódy, pro které se má opakovat požadavek
            allowed_methods=["GET"]  # Povolené metody pro retry
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
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
                
                # Nastavení SSL kontextu pro Google API
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Nastavení HTTP transportu s vlastním SSL kontextem
                http = urllib3.PoolManager(
                    ssl_context=ssl_context,
                    retries=Retry(
                        total=5,
                        backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                    )
                )
                
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_path, scopes=self.SCOPES)
                
                # Výpis informací o credentials pro diagnostiku
                logging.info(f"Service account email: {self.credentials.service_account_email}")
                logging.info(f"Token URI: {self.credentials._token_uri}")
                
                # Vytvoření služby s vlastním HTTP transportem a retry logikou
                self.service = build('docs', 'v1', credentials=self.credentials)
                
                # Test připojení k API s opakováním při chybě
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        logging.info(f"Testing connection to Google Docs API with document ID: {self.DOCUMENT_ID} (pokus {retry_count + 1}/{max_retries})")
                        self.service.documents().get(documentId=self.DOCUMENT_ID).execute()
                        logging.info("Successfully connected to Google Docs API")
                        break
                    except (HttpError, ssl.SSLError, socket.error) as e:
                        retry_count += 1
                        logging.warning(f"Chyba při připojení k Google Docs API (pokus {retry_count}/{max_retries}): {e}")
                        if retry_count >= max_retries:
                            raise
                        time.sleep(5)  # Čekáme 5 sekund před dalším pokusem
                
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

    # Dekorátor pro opakování operace při chybě
    @backoff.on_exception(backoff.expo, 
                         (HttpError, ssl.SSLError, socket.error, ConnectionError),
                         max_tries=5,
                         jitter=backoff.full_jitter)
    def _execute_with_retry(self, request):
        """
        # Pomocná metoda pro provedení požadavku s automatickým opakováním při chybě
        # Parametry:
        #   request: objekt požadavku Google API
        # Returns:
        #   výsledek požadavku
        # Raises:
        #   HttpError: při problému s API po vyčerpání všech pokusů
        """
        try:
            return request.execute()
        except (ssl.SSLError, socket.error) as e:
            logging.warning(f"SSL/Socket chyba při komunikaci s Google API: {e}")
            # Přidáme krátkou pauzu před opakováním
            time.sleep(2)
            raise  # Necháme backoff dekorátor zpracovat opakování

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
            # Použití metody s opakováním při chybě
            document = self._execute_with_retry(
                self.service.documents().get(documentId=self.DOCUMENT_ID)
            )
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
            
            logging.info(f"Načteno {len(existing_urls)} existujících nabídek z Google Docs")
            return existing_urls
        except HttpError as err:
            logging.error(f"Chyba při načítání existujících nabídek: {err}")
            return []
        except Exception as e:
            logging.error(f"Neočekávaná chyba při načítání existujících nabídek: {e}")
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
        # Parametry:
        #   url: str - URL adresa nabídky
        # Returns:
        #   dict: slovník s detaily nabídky (společnost, lokalita, popis)
        # Raises:
        #   RequestException: při problému s HTTP požadavkem
        """
        try:
            logging.info(f"Stahuji detaily nabídky: {url}")
            
            # Přidání náhodného user-agent pro snížení pravděpodobnosti blokování
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'cs,en-US;q=0.7,en;q=0.3',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            # Použití session s retry logikou a timeout
            try:
                response = self.session.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
            except requests.exceptions.SSLError as ssl_err:
                logging.warning(f"SSL chyba při stahování {url}: {ssl_err}")
                # Zkusíme znovu s vypnutou SSL verifikací
                response = self.session.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
            except requests.exceptions.RequestException as req_err:
                logging.error(f"Chyba při stahování detailů nabídky {url}: {req_err}")
                # Zkusíme ještě jednou s delším timeoutem
                time.sleep(5)  # Počkáme 5 sekund
                response = self.session.get(url, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extrakce informací o společnosti
            company_element = soup.find('a', class_="Typography--link")
            company = company_element.text.strip() if company_element else "Neznámá společnost"
            
            # Extrakce lokality
            location_element = soup.find('span', class_="Typography--bodyMedium")
            location = location_element.text.strip() if location_element else "Neznámá lokalita"
            
            # Extrakce popisu
            description_element = soup.find('div', class_="Typography--bodyLarge")
            description = description_element.text.strip() if description_element else "Bez popisu"
            
            return {
                'company': company,
                'location': location,
                'description': description[:500] + '...' if len(description) > 500 else description  # Omezení délky popisu
            }
        except Exception as e:
            logging.error(f"Chyba při získávání detailů nabídky {url}: {e}")
            # Vrátíme alespoň částečné informace, pokud jsou k dispozici
            return {
                'company': "Chyba při načítání",
                'location': "Chyba při načítání",
                'description': f"Chyba při načítání detailů: {str(e)[:100]}..."
            }

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
            # Uložíme nabídky do lokálního souboru jako zálohu
            backup_file = os.path.join(script_dir, 'jobs_backup.json')
            try:
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(new_jobs, f, ensure_ascii=False, indent=2)
                logging.info(f"Záloha {len(new_jobs)} nabídek uložena do {backup_file}")
            except Exception as backup_err:
                logging.error(f"Chyba při ukládání zálohy: {backup_err}")
            
            # Získáme aktuální dokument s opakováním při chybě
            document = self._execute_with_retry(
                self.service.documents().get(documentId=self.DOCUMENT_ID)
            )
            
            # Připravíme obsah pro přidání
            requests = []
            
            # Přidáme nadpis s datem
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Zkusíme nejprve alternativní metodu - přidání obsahu na konec dokumentu
            try:
                logging.info("Používám alternativní metodu přidání obsahu na konec dokumentu")
                content = f"\n\nNové nabídky nalezené {current_date}:\n\n"
                for job in new_jobs:
                    content += f"• {job['title']} - {job['company']} ({job['location']})\n  {job['link']}\n  {job['description']}\n\n"
                
                # Rozdělíme obsah na menší části, pokud je příliš velký
                # Google Docs API má limit na velikost požadavku
                max_content_length = 50000  # Přibližný limit pro velikost obsahu
                content_parts = []
                
                if len(content) > max_content_length:
                    # Rozdělíme obsah na menší části
                    current_part = ""
                    for job in new_jobs:
                        job_text = f"• {job['title']} - {job['company']} ({job['location']})\n  {job['link']}\n  {job['description']}\n\n"
                        
                        # Pokud by přidání této nabídky překročilo limit, uložíme aktuální část a začneme novou
                        if len(current_part) + len(job_text) > max_content_length:
                            content_parts.append(current_part)
                            current_part = f"\n\nPokračování nabídek z {current_date}:\n\n" + job_text
                        else:
                            current_part += job_text
                    
                    # Přidáme poslední část, pokud není prázdná
                    if current_part:
                        content_parts.append(current_part)
                else:
                    content_parts = [content]
                
                # Přidáme první část s nadpisem
                first_part = f"\n\nNové nabídky nalezené {current_date}:\n\n"
                if content_parts:
                    # Přidáme obsah první části k nadpisu
                    first_part += content_parts[0].replace(f"\n\nPokračování nabídek z {current_date}:\n\n", "")
                    content_parts[0] = first_part
                else:
                    content_parts = [first_part]
                
                # Přidáme každou část obsahu samostatně
                for i, part in enumerate(content_parts):
                    try:
                        logging.info(f"Přidávám část {i+1}/{len(content_parts)} obsahu (velikost: {len(part)} znaků)")
                        
                        result = self._execute_with_retry(
                            self.service.documents().batchUpdate(
                                documentId=self.DOCUMENT_ID,
                                body={
                                    'requests': [{
                                        'insertText': {
                                            'endOfSegmentLocation': {},
                                            'text': part
                                        }
                                    }]
                                }
                            )
                        )
                        
                        logging.info(f"Úspěšně přidána část {i+1}/{len(content_parts)}")
                        time.sleep(2)  # Krátká pauza mezi částmi
                    except Exception as part_err:
                        logging.error(f"Chyba při přidávání části {i+1}: {part_err}")
                        # Pokračujeme další částí i v případě chyby
                
                logging.info(f"Úspěšně přidáno {len(new_jobs)} nových nabídek do Google Docs alternativní metodou")
                return
                
            except Exception as alt_err:
                logging.error(f"Alternativní metoda selhala: {alt_err}")
                logging.info("Zkusím původní metodu přidání obsahu")
            
            # Pokud alternativní metoda selže, zkusíme původní metodu
            
            # Přidáme nadpis s datem
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
                job_text = f"\n• {job['title']} - {job['company']} ({job['location']})\n  {job['link']}\n  {job['description']}\n"
                
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
            logging.info(f"Přidávám {len(new_jobs)} nových nabídek do Google Docs")
            
            # Rozdělíme požadavky na menší dávky, pokud je jich příliš mnoho
            # Google Docs API má limit na počet požadavků v jednom volání
            batch_size = 5  # Zmenšíme velikost dávky pro větší spolehlivost
            for i in range(0, len(requests), batch_size):
                batch_requests = requests[i:i+batch_size]
                try:
                    result = self._execute_with_retry(
                        self.service.documents().batchUpdate(
                            documentId=self.DOCUMENT_ID,
                            body={'requests': batch_requests}
                        )
                    )
                    logging.info(f"Úspěšně přidána dávka {i//batch_size + 1} z {(len(requests) + batch_size - 1)//batch_size}")
                    time.sleep(3)  # Delší pauza mezi dávkami
                except Exception as err:
                    logging.error(f"Chyba při aktualizaci dokumentu (dávka {i//batch_size + 1}): {err}")
                    # Pokud selže dávka, zkusíme přidat požadavky jeden po druhém
                    for j, req in enumerate(batch_requests):
                        try:
                            self._execute_with_retry(
                                self.service.documents().batchUpdate(
                                    documentId=self.DOCUMENT_ID,
                                    body={'requests': [req]}
                                )
                            )
                            logging.info(f"Úspěšně přidán požadavek {j+1} z dávky {i//batch_size + 1}")
                        except Exception as single_err:
                            logging.error(f"Chyba při přidání jednotlivého požadavku: {single_err}")
                        time.sleep(2)
            
            logging.info(f"Úspěšně přidáno {len(new_jobs)} nových nabídek do Google Docs")
            
        except HttpError as err:
            logging.error(f"Chyba při aktualizaci Google Docs: {err}")
            self._try_simple_append(new_jobs)
        except ssl.SSLError as ssl_err:
            logging.error(f"SSL chyba při aktualizaci Google Docs: {ssl_err}")
            self._try_simple_append(new_jobs)
        except socket.error as sock_err:
            logging.error(f"Socket chyba při aktualizaci Google Docs: {sock_err}")
            self._try_simple_append(new_jobs)
        except Exception as e:
            logging.error(f"Neočekávaná chyba při aktualizaci dokumentu: {e}")
            self._try_simple_append(new_jobs)
    
    def _try_simple_append(self, new_jobs):
        """
        # Nejjednodušší možná metoda pro přidání obsahu do dokumentu
        # Použije se jako poslední možnost, když všechny ostatní metody selžou
        # Parametry:
        #   new_jobs: list[dict] - seznam nových pracovních nabídek
        """
        try:
            logging.info("Zkouším nejjednodušší možnou metodu přidání obsahu")
            
            # Vytvoříme jednoduchý text s nabídkami
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"\n\nNové nabídky nalezené {current_date}:\n\n"
            
            # Přidáme jen základní informace o každé nabídce
            for job in new_jobs:
                content += f"• {job['title']} - {job['company']}\n  {job['link']}\n\n"
            
            # Použijeme nejjednodušší možný požadavek
            self._execute_with_retry(
                self.service.documents().batchUpdate(
                    documentId=self.DOCUMENT_ID,
                    body={
                        'requests': [{
                            'insertText': {
                                'endOfSegmentLocation': {},
                                'text': content
                            }
                        }]
                    }
                )
            )
            
            logging.info("Úspěšně přidán zjednodušený obsah do dokumentu")
        except Exception as e:
            logging.error(f"I nejjednodušší metoda přidání obsahu selhala: {e}")
            logging.error("Nabídky jsou uloženy v záložním souboru jobs_backup.json")

    def scrape_jobs(self):
        """
        # Hlavní metoda pro scrapování nabídek
        # Prochází všechny lokality a stránky s výsledky
        # Kontroluje duplicity a ukládá pouze nové nabídky
        # Returns:
        #   list[dict]: seznam nových pracovních nabídek
        """
        try:
            existing_jobs = self.get_existing_jobs()
            new_jobs = []
            
            # Pomocný set pro sledování již zpracovaných URL v rámci aktuálního běhu
            processed_urls = set(existing_jobs)
            
            logging.info(f"Začínám scrapování s {len(processed_urls)} již existujícími nabídkami")

            # Procházení všech zadaných lokalit
            for location, radius in self.locations:
                page = 1
                consecutive_empty_pages = 0
                max_empty_pages = 3  # Pokud 3 stránky po sobě nemají nové nabídky, ukončíme procházení
                max_pages = 50  # Maximální počet stránek pro procházení
                
                while page <= max_pages:
                    try:
                        # Sestavení URL pro aktuální stránku a lokalitu
                        url = f"https://www.jobs.cz/prace/{location}/?q[]={self.keyword}&locality[radius]={radius}"
                        if page > 1:
                            url += f"&page={page}"

                        logging.info(f"Stahuji nabídky pro lokalitu {location}, stránka {page}")
                        
                        # Přidání náhodného user-agent pro snížení pravděpodobnosti blokování
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'cs,en-US;q=0.7,en;q=0.3',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Cache-Control': 'max-age=0'
                        }
                        
                        # Použití session s retry logikou a timeout
                        try:
                            response = self.session.get(url, headers=headers, timeout=15, verify=False)
                            response.raise_for_status()
                        except requests.exceptions.SSLError as ssl_err:
                            logging.warning(f"SSL chyba při stahování {url}: {ssl_err}")
                            # Zkusíme znovu s vypnutou SSL verifikací
                            response = self.session.get(url, headers=headers, timeout=15, verify=False)
                            response.raise_for_status()
                        except requests.exceptions.RequestException as req_err:
                            logging.error(f"Chyba při stahování stránky {url}: {req_err}")
                            # Zkusíme ještě jednou s delším timeoutem
                            time.sleep(5)  # Počkáme 5 sekund
                            response = self.session.get(url, headers=headers, timeout=30, verify=False)
                            response.raise_for_status()
                            
                        soup = BeautifulSoup(response.content, 'html.parser')

                        jobs = soup.find_all('h2', class_="SearchResultCard__title")
                        
                        # Kontrola, zda stránka obsahuje nabídky
                        if not jobs:
                            logging.info(f"Žádné nabídky na stránce {page} pro lokalitu {location}")
                            consecutive_empty_pages += 1
                            if consecutive_empty_pages >= max_empty_pages:
                                logging.info(f"Ukončuji procházení pro lokalitu {location} - {max_empty_pages} prázdných stránek po sobě")
                                break
                            page += 1
                            time.sleep(2)
                            continue
                        
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
                        
                        # Kontrola, zda jsme dosáhli maximálního počtu stránek
                        if page > max_pages:
                            logging.warning(f"Dosažen maximální počet stránek ({max_pages}) pro lokalitu {location}")
                            break

                    except Exception as e:
                        logging.error(f"Chyba při scrapování stránky {page} pro lokalitu {location}: {e}")
                        # Pokračujeme další stránkou i v případě chyby
                        page += 1
                        time.sleep(5)  # Delší pauza po chybě
                        continue

            # Výpis souhrnných informací
            logging.info(f"Celkem nalezeno {len(new_jobs)} nových nabídek")
            
            if new_jobs:
                self.append_to_docs(new_jobs)
                return new_jobs
            else:
                logging.info("Nebyly nalezeny žádné nové nabídky")
                return []
                
        except Exception as e:
            logging.error(f"Kritická chyba při scrapování: {e}")
            return []

def main():
    """
    # Hlavní funkce programu
    # Definuje lokality pro vyhledávání a spouští scraping
    """
    try:
        # Definice lokalit a jejich radiusů
        locations = [
            ("plzen", 20),  # Plzeň s radiusem 20 km
            ("praha", 10)   # Praha s radiusem 10 km
        ]
        
        scraper = JobsScraper(locations)
        scraper.scrape_jobs()
        logging.info("Scraping dokončen úspěšně")
    except Exception as e:
        logging.error(f"Neočekávaná chyba v hlavní funkci: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 