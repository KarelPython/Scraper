import os
import json
from bs4 import BeautifulSoup
from datetime import datetime

def extract_job_details(html_file):
    """
    Extrahuje detaily nabídky práce z HTML souboru
    """
    print(f"Analyzuji HTML soubor: {html_file}")
    
    try:
        # Načtení HTML souboru
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print(f"HTML soubor načten (velikost: {len(html_content)} znaků)")
        
        # Parsování HTML pomocí BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extrakce všech dostupných informací
        details = {}
        
        # Extrakce názvu pozice
        print("Hledám název pozice...")
        title_element = None
        title_selectors = [
            ('h1', {"class": "Typography--heading1"}),
            ('h1', {}),
            ('h1', {"class": "jobad__title"}),
            ('h1', {"class": "jobad-title"}),
            ('div', {"class": "jobad__header"}),
            ('div', {"data-test": "jobad-title"})
        ]
        
        for tag, attrs in title_selectors:
            elements = soup.find_all(tag, attrs)
            for element in elements:
                if element and element.text.strip():
                    title_element = element
                    print(f"  Nalezen název pozice pomocí selektoru: {tag}, {attrs}")
                    break
            if title_element:
                break
        
        details['title'] = title_element.text.strip() if title_element else "Neznámý název pozice"
        print(f"Nalezen název pozice: {details['title']}")
        
        # Extrakce informací o společnosti
        print("Hledám informace o společnosti...")
        company_element = None
        company_selectors = [
            ('a', {"class": "Typography--link"}),
            ('div', {"data-test": "jd-company-name"}),
            ('div', {"class": "jobad__company"}),
            ('span', {"class": "jobad__company-name"}),
            ('div', {"class": "company-name"})
        ]
        
        for tag, attrs in company_selectors:
            elements = soup.find_all(tag, attrs)
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
        
        # Extrakce lokality
        print("Hledám lokalitu...")
        location_element = None
        location_selectors = [
            ('span', {"class": "Typography--bodyMedium"}),
            ('div', {"data-test": "jd-locality"}),
            ('div', {"class": "jobad__location"}),
            ('span', {"class": "jobad__location"}),
            ('div', {"class": "location"})
        ]
        
        for tag, attrs in location_selectors:
            elements = soup.find_all(tag, attrs)
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
        
        # Extrakce platu
        print("Hledám informace o platu...")
        salary_element = None
        salary_selectors = [
            ('div', {"data-test": "jd-salary"}),
            ('div', {"class": "jobad__salary"}),
            ('span', {"class": "jobad__salary"}),
            ('div', {"class": "salary"})
        ]
        
        for tag, attrs in salary_selectors:
            elements = soup.find_all(tag, attrs)
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
        
        # Extrakce popisu pozice
        print("Hledám popis pozice...")
        description_element = None
        description_selectors = [
            ('div', {"data-test": "jd-body-richtext"}),
            ('div', {"class": "Typography--bodyLarge"}),
            ('div', {"class": "jobad__body"}),
            ('div', {"class": "jobad-description"}),
            ('div', {"class": "description"})
        ]
        
        for tag, attrs in description_selectors:
            elements = soup.find_all(tag, attrs)
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
        
        # Extrakce požadavků
        print("Hledám požadavky...")
        requirements_element = None
        requirements_selectors = [
            ('div', {"data-test": "jd-requirements-richtext"}),
            ('div', {"class": "jobad__requirements"}),
            ('div', {"class": "requirements"})
        ]
        
        for tag, attrs in requirements_selectors:
            elements = soup.find_all(tag, attrs)
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
            ('div', {"class": "jobad__employment"}),
            ('div', {"class": "employment-type"})
        ]
        
        for tag, attrs in job_type_selectors:
            elements = soup.find_all(tag, attrs)
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
        
        # Extrakce benefitů
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
        
        print(f"Úspěšně extrahována data z HTML souboru")
        
        # Uložení výsledků do JSON souboru
        output_file = f"extracted_job_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(details, f, ensure_ascii=False, indent=4)
        
        print(f"Výsledky uloženy do souboru: {output_file}")
        
        return details
        
    except Exception as e:
        print(f"Chyba při extrakci dat z HTML souboru: {e}")
        return None

if __name__ == "__main__":
    # Název HTML souboru s nabídkou práce
    html_file = "html.txt"
    
    # Kontrola existence souboru
    if not os.path.exists(html_file):
        print(f"Soubor {html_file} neexistuje!")
        exit(1)
    
    # Extrakce dat
    job_details = extract_job_details(html_file)
    
    # Výpis výsledků
    if job_details:
        print("\n=== VÝSLEDKY EXTRAKCE ===")
        for key, value in job_details.items():
            if isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                if len(str(value)) > 100:
                    print(f"{key}: {str(value)[:100]}...")
                else:
                    print(f"{key}: {value}")
    else:
        print("Extrakce dat selhala!") 