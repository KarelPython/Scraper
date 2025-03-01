import os
import sys
import logging
import requests
import json
from bs4 import BeautifulSoup
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import ssl
import socket
from datetime import datetime

# Nastavení logování
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Potlačení varování o nezabezpečených požadavcích
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Nastavení delšího timeoutu pro socket
socket.setdefaulttimeout(60)  # 60 sekund timeout

class JobDetailsTester:
    def __init__(self):
        """
        Inicializace testeru pro extrakci detailů nabídek práce
        """
        print("Inicializace JobDetailsTester")
        # Nastavení session s retry logikou
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get_job_details(self, url):
        """
        Získá detailní informace o pracovní nabídce z její stránky
        """
        print(f"\nStahuji detaily nabídky: {url}")
        
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
            
            # Použití session s retry logikou a timeout
            try:
                print("Odesílám HTTP požadavek...")
                response = self.session.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
                print(f"Odpověď serveru: {response.status_code}")
            except requests.exceptions.SSLError as ssl_err:
                print(f"SSL chyba při stahování {url}: {ssl_err}")
                # Zkusíme znovu s vypnutou SSL verifikací
                response = self.session.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
            except requests.exceptions.RequestException as req_err:
                print(f"Chyba při stahování detailů nabídky {url}: {req_err}")
                # Zkusíme ještě jednou s delším timeoutem
                time.sleep(5)  # Počkáme 5 sekund
                response = self.session.get(url, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
            
            # Uložení HTML kódu pro diagnostiku
            print("Ukládám HTML kód stránky pro diagnostiku...")
            with open('last_job_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"HTML kód stránky uložen do souboru last_job_page.html (velikost: {len(response.text)} znaků)")
                
            soup = BeautifulSoup(response.content, 'html.parser')
            print(f"HTML parsován pomocí BeautifulSoup")
            
            # Extrakce všech dostupných informací
            details = {}
            
            # Extrakce názvu pozice - zkusíme více možných selektorů
            print("Hledám název pozice...")
            title_element = None
            title_selectors = [
                ('h1', {"class_": "Typography--heading1"}),
                ('h1', {}),
                ('h1', {"class_": "jobad__title"}),
                ('h1', {"class_": "jobad-title"}),
                ('div', {"class_": "jobad__header"}),
                ('div', {"data-test": "jobad-title"})
            ]
            
            for tag, attrs in title_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip():
                        title_element = element
                        print(f"  Nalezen název pozice pomocí selektoru: {tag}, {attrs}")
                        break
                if title_element:
                    break
            
            details['title'] = title_element.text.strip() if title_element else "Neznámý název pozice"
            print(f"Nalezen název pozice: {details['title']}")
            
            # Extrakce informací o společnosti - zkusíme více možných selektorů
            print("Hledám informace o společnosti...")
            company_element = None
            company_selectors = [
                ('a', {"class_": "Typography--link"}),
                ('div', {"data-test": "jd-company-name"}),
                ('div', {"class_": "jobad__company"}),
                ('span', {"class_": "jobad__company-name"}),
                ('div', {"class_": "company-name"})
            ]
            
            for tag, attrs in company_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip():
                        company_element = element
                        print(f"  Nalezena společnost pomocí selektoru: {tag}, {attrs}")
                        break
                if company_element:
                    break
                    
            # Pokud jsme nenašli společnost podle selektorů, zkusíme najít podle textu
            if not company_element:
                print("  Hledám společnost podle textu...")
                company_labels = soup.find_all(string=lambda text: text and ('Společnost:' in text or 'Firma:' in text))
                for label in company_labels:
                    parent = label.parent
                    next_element = parent.find_next()
                    if next_element and next_element.text.strip():
                        company_element = next_element
                        print(f"  Nalezena společnost podle textu: {label}")
                        break
            
            details['company'] = company_element.text.strip() if company_element else "Neznámá společnost"
            print(f"Nalezena společnost: {details['company']}")
            
            # Extrakce lokality - zkusíme více možných selektorů
            print("Hledám lokalitu...")
            location_element = None
            location_selectors = [
                ('span', {"class_": "Typography--bodyMedium"}),
                ('div', {"data-test": "jd-locality"}),
                ('div', {"class_": "jobad__location"}),
                ('span', {"class_": "jobad__location"}),
                ('div', {"class_": "location"})
            ]
            
            for tag, attrs in location_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip():
                        # Kontrola, zda text obsahuje typické znaky pro lokalitu
                        text = element.text.strip().lower()
                        if any(city in text for city in ['praha', 'brno', 'ostrava', 'plzeň', 'liberec', 'olomouc', 'české', 'hradec']):
                            location_element = element
                            print(f"  Nalezena lokalita pomocí selektoru: {tag}, {attrs}")
                            break
                if location_element:
                    break
                    
            # Pokud jsme nenašli lokalitu podle selektorů, zkusíme najít podle textu
            if not location_element:
                print("  Hledám lokalitu podle textu...")
                location_labels = soup.find_all(string=lambda text: text and ('Lokalita:' in text or 'Místo výkonu práce:' in text))
                for label in location_labels:
                    parent = label.parent
                    next_element = parent.find_next()
                    if next_element and next_element.text.strip():
                        location_element = next_element
                        print(f"  Nalezena lokalita podle textu: {label}")
                        break
            
            details['location'] = location_element.text.strip() if location_element else "Neznámá lokalita"
            print(f"Nalezena lokalita: {details['location']}")
            
            # Extrakce platu - zkusíme více možných selektorů
            print("Hledám informace o platu...")
            salary_element = None
            salary_selectors = [
                ('div', {"data-test": "jd-salary"}),
                ('div', {"class_": "jobad__salary"}),
                ('span', {"class_": "jobad__salary"}),
                ('div', {"class_": "salary"})
            ]
            
            for tag, attrs in salary_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip():
                        # Kontrola, zda text obsahuje typické znaky pro plat
                        text = element.text.strip().lower()
                        if any(currency in text for currency in ['kč', 'czk', ',-', 'měsíčně', 'plat']):
                            salary_element = element
                            print(f"  Nalezen plat pomocí selektoru: {tag}, {attrs}")
                            break
                if salary_element:
                    break
                    
            # Pokud jsme nenašli plat podle selektorů, zkusíme najít podle textu
            if not salary_element:
                print("  Hledám plat podle textu...")
                salary_labels = soup.find_all(string=lambda text: text and ('Plat:' in text or 'Mzda:' in text))
                for label in salary_labels:
                    parent = label.parent
                    next_element = parent.find_next()
                    if next_element and next_element.text.strip():
                        salary_element = next_element
                        print(f"  Nalezen plat podle textu: {label}")
                        break
            
            details['salary'] = salary_element.text.strip() if salary_element else "Neuvedeno"
            print(f"Nalezen plat: {details['salary']}")
            
            # Extrakce popisu pozice - zkusíme více možných selektorů
            print("Hledám popis pozice...")
            description_element = None
            description_selectors = [
                ('div', {"data-test": "jd-body-richtext"}),
                ('div', {"class_": "Typography--bodyLarge"}),
                ('div', {"class_": "jobad__body"}),
                ('div', {"class_": "jobad-description"}),
                ('div', {"class_": "description"})
            ]
            
            for tag, attrs in description_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip() and len(element.text.strip()) > 100:
                        description_element = element
                        print(f"  Nalezen popis pozice pomocí selektoru: {tag}, {attrs}")
                        break
                if description_element:
                    break
                    
            # Pokud jsme nenašli popis podle selektorů, zkusíme najít podle textu
            if not description_element:
                print("  Hledám popis podle textu...")
                description_labels = soup.find_all(string=lambda text: text and ('Náplň práce:' in text or 'Popis pozice:' in text))
                for label in description_labels:
                    parent = label.parent
                    next_element = parent.find_next()
                    if next_element and next_element.text.strip():
                        description_element = next_element
                        print(f"  Nalezen popis podle textu: {label}")
                        break
                        
            # Pokud stále nemáme popis, zkusíme najít jakýkoliv dlouhý text v dokumentu
            if not description_element:
                print("  Hledám jakýkoliv dlouhý text jako popis...")
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    if p and p.text.strip() and len(p.text.strip()) > 100:
                        description_element = p
                        print(f"  Nalezen popis jako dlouhý odstavec")
                        break
            
            details['description'] = description_element.text.strip() if description_element else "Neuvedeno"
            if len(details['description']) > 1000:
                print(f"Nalezen popis pozice (zkráceno): {details['description'][:100]}...")
            else:
                print(f"Nalezen popis pozice: {details['description']}")
            
            # Extrakce požadavků - zkusíme více možných selektorů
            print("Hledám požadavky...")
            requirements_element = None
            requirements_selectors = [
                ('div', {"data-test": "jd-requirements-richtext"}),
                ('div', {"class_": "jobad__requirements"}),
                ('div', {"class_": "requirements"})
            ]
            
            for tag, attrs in requirements_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip():
                        requirements_element = element
                        print(f"  Nalezeny požadavky pomocí selektoru: {tag}, {attrs}")
                        break
                if requirements_element:
                    break
                    
            # Pokud jsme nenašli požadavky podle selektorů, zkusíme najít podle textu
            if not requirements_element:
                print("  Hledám požadavky podle textu...")
                requirements_labels = soup.find_all(string=lambda text: text and ('Požadavky:' in text or 'Požadujeme:' in text))
                for label in requirements_labels:
                    parent = label.parent
                    next_element = parent.find_next()
                    if next_element and next_element.text.strip():
                        requirements_element = next_element
                        print(f"  Nalezeny požadavky podle textu: {label}")
                        break
            
            details['requirements'] = requirements_element.text.strip() if requirements_element else "Neuvedeno"
            if requirements_element:
                print(f"Nalezeny požadavky: {details['requirements'][:100]}...")
            
            # Extrakce typu úvazku
            print("Hledám typ úvazku...")
            job_type_element = None
            job_type_selectors = [
                ('div', {"data-test": "jd-employment"}),
                ('div', {"class_": "jobad__employment"}),
                ('div', {"class_": "employment-type"})
            ]
            
            for tag, attrs in job_type_selectors:
                print(f"  Zkouším selektor: {tag}, {attrs}")
                elements = soup.find_all(tag, **attrs)
                for element in elements:
                    if element and element.text.strip():
                        job_type_element = element
                        print(f"  Nalezen typ úvazku pomocí selektoru: {tag}, {attrs}")
                        break
                if job_type_element:
                    break
                    
            # Pokud jsme nenašli typ úvazku podle selektorů, zkusíme najít podle textu
            if not job_type_element:
                print("  Hledám typ úvazku podle textu...")
                job_type_labels = soup.find_all(string=lambda text: text and ('Úvazek:' in text or 'Typ práce:' in text))
                for label in job_type_labels:
                    parent = label.parent
                    next_element = parent.find_next()
                    if next_element and next_element.text.strip():
                        job_type_element = next_element
                        print(f"  Nalezen typ úvazku podle textu: {label}")
                        break
            
            details['job_type'] = job_type_element.text.strip() if job_type_element else "Neuvedeno"
            if job_type_element:
                print(f"Nalezen typ úvazku: {details['job_type']}")
            
            # Extrakce benefitů - zkusíme více možných selektorů
            print("Hledám benefity...")
            benefits = []
            benefits_elements = soup.find_all('div', class_="Benefit")
            if benefits_elements:
                print(f"  Nalezeno {len(benefits_elements)} benefitů pomocí třídy 'Benefit'")
                for benefit in benefits_elements:
                    benefit_text = benefit.text.strip()
                    if benefit_text:
                        benefits.append(benefit_text)
                        
            # Pokud jsme nenašli benefity podle třídy, zkusíme najít podle textu
            if not benefits:
                print("  Hledám benefity podle textu...")
                benefits_section = None
                benefits_headers = soup.find_all(string=lambda text: text and ('Benefity:' in text or 'Nabízíme:' in text))
                for header in benefits_headers:
                    parent = header.parent
                    benefits_section = parent.find_next('ul')
                    if benefits_section:
                        print(f"  Nalezen seznam benefitů podle textu: {header}")
                        for li in benefits_section.find_all('li'):
                            benefit_text = li.text.strip()
                            if benefit_text:
                                benefits.append(benefit_text)
                        break
            
            details['benefits'] = benefits if benefits else ["Neuvedeno"]
            if benefits:
                print(f"Nalezeno {len(benefits)} benefitů")
            
            # Kontrola a čištění dat
            print("Čištění a kontrola dat...")
            for key, value in details.items():
                if isinstance(value, str):
                    # Odstranění nadbytečných bílých znaků
                    details[key] = ' '.join(value.split())
                    # Kontrola prázdných hodnot
                    if not details[key] or details[key].lower() in ['neuvedeno', 'neznámý', 'neznámá', 'neznámé']:
                        details[key] = "Neuvedeno"
            
            # Omezení délky dlouhých textů
            for key in ['description', 'requirements']:
                if len(details.get(key, "")) > 2000:
                    details[key] = details[key][:2000] + "..."
            
            print(f"Úspěšně staženy detaily nabídky: {url}")
            return details
            
        except Exception as e:
            print(f"Chyba při získávání detailů nabídky {url}: {e}")
            # Vrátíme alespoň částečné informace, pokud jsou k dispozici
            return {
                'company': "Chyba při načítání",
                'location': "Chyba při načítání",
                'description': f"Chyba při načítání detailů: {str(e)[:100]}..."
            }
    
    def save_to_file(self, job_details, filename):
        """
        Uloží detaily nabídky do JSON souboru
        """
        try:
            print(f"Ukládám detaily do souboru: {filename}")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(job_details, f, ensure_ascii=False, indent=4)
            print(f"Detaily úspěšně uloženy do souboru: {filename}")
            return True
        except Exception as e:
            print(f"Chyba při ukládání detailů do souboru: {e}")
            return False

if __name__ == "__main__":
    print("=== TEST EXTRAKCE DETAILŮ NABÍDEK PRÁCE ===")
    
    # Seznam URL adres k otestování
    test_urls = [
        "https://www.jobs.cz/rpd/1694307246/",
        "https://www.jobs.cz/rpd/1694307246/?rps=233",
        "https://www.jobs.cz/pd/1694307246/",
        "https://www.jobs.cz/fp/index.php?offer_id=1694307246&position_id=1694307246",
        # Obecnější URL, které by měly být stabilnější
        "https://www.jobs.cz/prace/python/",
        "https://www.jobs.cz/prace/praha/",
        "https://www.jobs.cz/prace/brno/"
    ]
    
    print("Spouštím test extrakce detailů nabídek práce")
    tester = JobDetailsTester()
    
    # Zkusíme stáhnout detaily z každé URL
    for url in test_urls:
        print(f"\n=== Testuji URL: {url} ===")
        try:
            # Pokusíme se získat detaily nabídky
            job_details = tester.get_job_details(url)
            
            # Vypíšeme získané detaily
            print(f"\n=== Získané detaily pro {url}: ===")
            for key, value in job_details.items():
                if isinstance(value, list):
                    print(f"  {key}: {len(value)} položek")
                    for item in value[:3]:  # Zobrazíme jen první 3 položky
                        print(f"    - {item}")
                    if len(value) > 3:
                        print(f"    - ... a dalších {len(value) - 3} položek")
                else:
                    # Zkrátíme dlouhé texty pro výpis
                    if isinstance(value, str) and len(value) > 100:
                        print(f"  {key}: {value[:100]}...")
                    else:
                        print(f"  {key}: {value}")
            
            # Uložíme detaily do JSON souboru
            filename = f"job_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            tester.save_to_file(job_details, filename)
            
            # Pokud jsme úspěšně získali detaily, můžeme přestat zkoušet další URL
            if job_details and job_details.get('title') != "Neznámý název pozice" and job_details.get('description') != "Neuvedeno":
                print(f"\nÚspěšně získány detaily z URL: {url}")
                break
        except Exception as e:
            print(f"Chyba při testování URL {url}: {e}")
            continue
    
    print("\n=== Test dokončen ===") 