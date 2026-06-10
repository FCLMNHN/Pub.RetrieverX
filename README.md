# Pub.RetrieverX

**Pub.retrieverX** est un script Python automatisé permettant d'extraire les publications scientifiques de chercheurs à partir d'un fichier Excel, d'enrichir leurs métadonnées (titres, abstracts/descriptions) via des APIs académiques et du scraping, et d'identifier précisément l'**entrepôt ou éditeur initial** de publication.

---

## 📋 Fonctionnalités & Pipeline d'Enrichissement

Le script traite une liste de chercheurs et applique une pipeline robuste à trois niveaux pour maximiser le taux de complétion des données :

### 1. Extraction depuis ORCID
- Recherche de l'identifiant **ORCID** unique du chercheur à partir de son Nom et Prénom.
- Récupération de la liste de ses travaux (travaux récents, articles, rapports).
- Extraction sécurisée des métadonnées de base : Titre fourni, URL associée, Date de publication, et le **DOI** (Digital Object Identifier) si disponible.

### 2. Pipeline d'Enrichissement (Abstract & Titre propre)
Pour chaque publication trouvée, le script cherche à récupérer un résumé (*abstract*) et un titre nettoyé en suivant cet ordre de priorité :
- **Règle 1 :** Si un DOI est présent, interrogation directe de l'API **Semantic Scholar**.
- **Règle 2 :** Si le DOI est absent ou échoue, recherche par texte flou via le **Titre** sur l'API Semantic Scholar (limité au résultat le plus pertinent).
- **Règle 3 :** Si les deux étapes précédentes échouent, la bibliothèque **Trafilatura** prend le relais pour scraper le contenu textuel directement depuis l'URL de la publication.

### 3. Résolution de l'Entrepôt / Éditeur Initial
Le script ne se contente pas de lire l'URL (qui pointe souvent vers un dépôt secondaire ou une archive ouverte comme HAL). Il détermine la **source originale** :
- **Via DOI :** Interrogation en arrière-plan de l'API **Crossref** pour obtenir le nom officiel de l'éditeur d'origine (ex: *Elsevier*, *Springer*, *Wiley*) et le nom de la revue.
- **Via URL HAL :** Si l'URL provient de HAL, le script utilise l'**API interne de HAL** pour vérifier si le document est lié à une revue scientifique éditée ailleurs, afin de remonter à la source initiale.
- **Via URL Générique :** Analyse des mots-clés du domaine ou scraping des balises métadonnées HTML (`citation_publisher`) via Trafilatura.

---

## 🛠️ Prérequis et Installation

### Dépendances
Le projet nécessite Python 3.7+ et les bibliothèques suivantes :
- `pandas` & `openpyxl` (pour la lecture du fichier Excel input)
- `requests` (pour les appels d'API)
- `trafilatura` (pour le scraping de secours et l'extraction des métadonnées web)

### Installation
1. Clonez ce dépôt ou téléchargez le script.
