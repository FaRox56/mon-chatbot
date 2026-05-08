import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# URL de base
base_url = "https://www.auto-ecole-savoie.com/"
visited = set()
to_visit = [base_url]
max_pages = 20
all_content = ""

def is_internal(url):
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)
    return parsed.netloc == base_parsed.netloc or parsed.netloc == ''

while to_visit and len(visited) < max_pages:
    current_url = to_visit.pop(0)
    if current_url in visited:
        continue
    visited.add(current_url)

    try:
        response = requests.get(current_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Titre de la page
        title = soup.title.string if soup.title else "Sans titre"
        all_content += f"=== {title} ===\n"

        # Extraire et nettoyer le texte
        text = soup.get_text()
        cleaned_text = ' '.join(text.split())
        all_content += cleaned_text + "\n\n"

        # Trouver les liens internes
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(current_url, href)
            if is_internal(full_url) and full_url not in visited and full_url not in to_visit:
                to_visit.append(full_url)

    except Exception as e:
        print(f"Erreur sur {current_url}: {e}")

# Sauvegarder dans context.txt
with open('context.txt', 'w', encoding='utf-8') as f:
    f.write(all_content)

print(f"Contenu récupéré de {len(visited)} pages : {len(all_content)} caractères")