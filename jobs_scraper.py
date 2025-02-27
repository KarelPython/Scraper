import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import logging
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os

# Nastavení logování pro sledování průběhu scrapování a případných chyb
# Logy se ukládají do souboru scraper.log a zároveň se zobrazují v konzoli
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

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
        
        # Nastavení Google Docs API
        self.SCOPES = ['https://www.googleapis.com/auth/documents']
        self.DOCUMENT_ID = os.getenv('DOCUMENT_ID')
        self.credentials = service_account.Credentials.from_service_account_file(
            'credentials.json', scopes=self.SCOPES)
        self.service = build('docs', 'v1', credentials=self.credentials)

    def get_existing_jobs(self):
        """
        # Načte existující nabídky z Google Docs pro kontrolu duplicit
        # Vrací seznam URL adres již existujících nabídek
        # Returns:
        #   list[str]: seznam URL adres existujících nabídek
        # Raises:
        #   HttpError: při problému s připojením ke Google Docs
        """
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
            if link and not link.startswith('http'):
                link = 'https://www.jobs.cz' + link
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

        # Procházení všech zadaných lokalit
        for location, radius in self.locations:
            page = 1
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
                    if not jobs:
                        break

                    for job in jobs:
                        title, link = self.parse_job_listing(job)
                        if not title or not link:
                            continue

                        # Kontrola duplicit
                        if link not in existing_jobs:
                            details = self.get_job_details(link)
                            if details:
                                job_data = {
                                    'title': title,
                                    'link': link,
                                    **details
                                }
                                new_jobs.append(job_data)
                                logging.info(f"Nalezena nová nabídka: {title} v {location}")
                                time.sleep(1)  # Prodleva mezi požadavky

                    page += 1
                    time.sleep(2)  # Prodleva mezi stránkami

                except Exception as e:
                    logging.error(f"Chyba při scrapování stránky {page} pro lokalitu {location}: {e}")
                    break

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