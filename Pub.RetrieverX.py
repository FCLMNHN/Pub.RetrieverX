import pandas as pd
import requests
import json
import time
import re
from urllib.parse import urlparse
import trafilatura 

# =====================================================================
# 1. FONCTIONS DE RECHERCHE D'IDENTIFIANTS ET D'ABSTRACTS (ORCID & SEMANTIC SCHOLAR)
# =====================================================================

def get_orcid_ids(prenom, nom):
    url = "https://pub.orcid.org/v3.0/expanded-search/"
    query = f'given-names:"{prenom}" AND family-name:"{nom}"'
    headers = {'Accept': 'application/json'}
    try:
        response = requests.get(url, params={'q': query}, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json().get('expanded-result', []) or []
            return [res.get('orcid-id') for res in results if res.get('orcid-id')]
    except Exception as e:
        print(f"  Erreur API recherche : {e}")
    return []

def fetch_semantic_scholar_by_doi(doi):
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {"fields": "title,abstract"}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('title'), data.get('abstract')
    except Exception:
        pass
    return None, None

def fetch_semantic_scholar_by_title(title):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": title, "limit": 1, "fields": "title,abstract"}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('data', [])
            if results:
                return results[0].get('title'), results[0].get('abstract')
    except Exception:
        pass
    return None, None

def fetch_via_trafilatura(target_url):
    if not target_url:
        return None, None
    try:
        downloaded = trafilatura.fetch_url(target_url)
        if downloaded:
            content = trafilatura.extract(downloaded)
            metadata = trafilatura.extract_metadata(downloaded)
            title = metadata.title if metadata else "Titre inconnu (Scraping)"
            return title, content
    except Exception:
        pass
    return None, None

# =====================================================================
# 2. FONCTIONS DE DÉTECTION DE L'ENTREPÔT / ÉDITEUR INITIAL
# =====================================================================

def get_original_publisher(doi):
    """Interroge l'API Crossref pour trouver l'éditeur d'origine via le DOI."""
    if not doi:
        return None
    url = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": "PubRetriever/1.0 (mailto:votre.email@domaine.com)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            message = response.json().get('message', {})
            publisher = message.get('publisher')
            container = message.get('container-title', [])
            journal_name = container[0] if container else None
            
            if publisher and journal_name:
                return f"{publisher} ({journal_name})"
            return publisher
    except Exception:
        pass
    return None

def get_origin_from_hal_api(hal_url):
    """Interroge l'API interne de HAL pour savoir d'où vient l'article (Revue/Éditeur)."""
    match = re.search(r'(hal-\d+|mnhn-\d+|anses-\d+)', hal_url)
    if not match:
        return None
    hal_id = match.group(1)
    
    # On extrait uniquement les chiffres pour l'interrogation de l'API HAL
    doc_id = hal_id.split('-')[-1]
    api_url = f"https://api.archives-ouvertes.fr/search/?q=docid:{doc_id}&wt=json&fl=publisher_s,journalTitle_s"
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            docs = response.json().get('response', {}).get('docs', [])
            if docs:
                data = docs[0]
                journal = data.get('journalTitle_s')
                publisher = data.get('publisher_s')
                
                if journal:
                    return f"Éditeur d'origine (Revue : {journal})"
                elif publisher:
                    # 'publisher_s' est souvent renvoyé sous forme de liste par l'API HAL
                    pub_name = publisher[0] if isinstance(publisher, list) else publisher
                    return f"Éditeur d'origine : {pub_name}"
    except Exception:
        pass
    return "Dépot direct HAL (sans éditeur commercial)"

def detect_publisher_by_url(url):
    """Analyse rapide par mot-clé dans le domaine de l'URL."""
    if not url:
        return "Entrepôt inconnu"
    domain = urlparse(url).netloc.lower()
    
    if "hal." in domain:
        return "HAL (Archive ouverte)"
    elif "zenodo" in domain:
        return "Zenodo (CERN)"
    elif "biorxiv" in domain:
        return "bioRxiv (Preprint)"
    elif "arxiv.org" in domain:
        return "arXiv"
    elif "researchgate" in domain:
        return "ResearchGate"
    elif "github" in domain:
        return "GitHub"
    elif "sciencedirect" in domain or "elsevier" in domain:
        return "Elsevier (ScienceDirect)"
    elif "springer" in domain:
        return "Springer"
    elif "wiley" in domain:
        return "Wiley Online Library"
    
    return f"Plateforme externe ({domain.replace('www.', '')})"

def get_publisher_from_html(url):
    """Extrait l'éditeur depuis les métadonnées HTML cachées de la page (via Trafilatura)."""
    if not url:
        return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            metadata = trafilatura.extract_metadata(downloaded)
            if metadata and metadata.publisher:
                return metadata.publisher
    except Exception:
        pass
    return None

def resolve_origin(doi, url):
    """Fonction maîtresse guidant la pipeline de détection d'origine."""
    # 1. Priorité absolue : Crossref via le DOI
    if doi:
        publisher_via_doi = get_original_publisher(doi)
        if publisher_via_doi:
            return publisher_via_doi
            
    # 2. Cas spécifique HAL : On demande à son API la revue d'origine
    if url and "hal." in url:
        origin_from_hal = get_origin_from_hal_api(url)
        if origin_from_hal:
            return origin_from_hal

    # 3. Heuristique par mots-clés sur l'URL pour les autres plateformes connues
    if url:
        origin_via_url = detect_publisher_by_url(url)
        if "Plateforme externe" not in origin_via_url:
            return origin_via_url
            
    # 4. Dernier recours : Trafilatura (Scraping des balises meta du site)
    if url:
        scraped_publisher = get_publisher_from_html(url)
        if scraped_publisher:
            return scraped_publisher
        return detect_publisher_by_url(url) # Renvoie au moins le nom du domaine si échec
        
    return "Source introuvable"

# =====================================================================
# 3. FONCTION DE TRAITEMENT DES TRAVAUX ET COEUR DU SCRIPT
# =====================================================================

def get_works_data(orcid_id):
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    headers = {'Accept': 'application/json'}
    works_list = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json() or {}
            groups = data.get('group', []) or []
            
            for group in groups:
                if not group:
                    continue
                
                summaries = group.get('work-summary', []) or [{}]
                summary = summaries[0] or {}
                
                title_node = summary.get('title') or {}
                title_main = title_node.get('title') or {}
                title_value = title_main.get('value')
                
                url_node = summary.get('url') or {}
                url_value = url_node.get('value')
                
                pub_date = summary.get('publication-date') or {}
                year_value = (pub_date.get('year') or {}).get('value')
                month_value = (pub_date.get('month') or {}).get('value')
                day_value = (pub_date.get('day') or {}).get('value')
                
                ext_ids_node = summary.get('external-ids') or {}
                ext_id_list = ext_ids_node.get('external-id') or []
                doi_value = None

                for ext_id in ext_id_list:
                    if ext_id and ext_id.get('external-id-type') == 'doi':
                        doi_value = ext_id.get('external-id-value')
                        break

                # --- PIPELINE ENRICHISSEMENT (Title & Description / Abstracts) ---
                final_title = None
                final_abstract = None
                
                # Condition 1 : Recherche par DOI
                if doi_value:
                    print(f"    -> Récupération abstract via DOI: {doi_value}")
                    final_title, final_abstract = fetch_semantic_scholar_by_doi(doi_value)
                    time.sleep(1.1)  # Respect du rate-limit sans clé API

                # Condition 2 : Recherche par Titre si le DOI a échoué ou n'existe pas
                if not final_abstract and title_value:
                    print(f"    -> Récupération abstract via Titre...")
                    final_title, final_abstract = fetch_semantic_scholar_by_title(title_value)
                    time.sleep(1.1)

                # Condition 3 : Secours Trafilatura
                if not final_abstract and url_value:
                    print(f"    -> Récupération de secours via Trafilatura...")
                    scraped_title, scraped_content = fetch_via_trafilatura(url_value)
                    final_title = final_title or scraped_title
                    final_abstract = scraped_content

                resolved_title = final_title or title_value or "Sans titre"
                resolved_description = final_abstract or "Aucun abstract ou description disponible."
                
                # --- NOUVEAUTÉ : Détermination de la source / entrepôt initial ---
                print(f"    -> Détermination de l'entrepôt initial...")
                publisher_origin = resolve_origin(doi_value, url_value)
                
                works_list.append({
                    "common:title": title_value,
                    "title": resolved_title,
                    "description": resolved_description,
                    "work:type": summary.get('type'),
                    "common:external-id-url": url_value,
                    "common:doi": doi_value,
                    "common:publisher_origin": publisher_origin, # <-- Ajout de la clé dans le JSON
                    "common:year": year_value,
                    "common:month": month_value,
                    "common:day": day_value
                })
    except Exception as e:
        print(f"  Erreur API travaux ({orcid_id}) : {e}")
    return works_list

def process_excel_to_json(input_excel, output_json):
    try:
        df = pd.read_excel(input_excel)
    except Exception as e:
        print(f"Impossible de lire le fichier Excel : {e}")
        return

    final_output = []

    for index, row in df.iterrows():
        raw_prenom = str(row['Prénom']).replace(';', '').replace(',', '').strip()
        raw_nom = str(row['Nom']).replace(';', '').replace(',', '').strip()
        
        if not raw_prenom or not raw_nom or raw_prenom == "nan":
            continue

        print(f"[{index+1}] Recherche : {raw_prenom} {raw_nom}...")
        
        orcids = get_orcid_ids(raw_prenom, raw_nom)
        
        if not orcids:
            print(f"  - Aucun résultat.")
            continue

        for orcid in orcids:
            print(f"  - Extraction pour {orcid}...")
            publications = get_works_data(orcid)
            
            final_output.append({
                "Nom": raw_nom,
                "Prénom": raw_prenom,
                "Orc-ID": orcid,
                "activities:group": publications
            })
            time.sleep(0.3)

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)
    
    print(f"\nTraitement terminé. Résultats sauvegardés dans : {output_json}")

# =====================================================================
# 4. EXÉCUTION
# =====================================================================
if __name__ == "__main__":
    process_excel_to_json('chercheurs.xlsx', 'data_orcid_complet.json')