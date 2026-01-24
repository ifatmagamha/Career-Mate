# RecruitAI — Documentation des Agents

## 1. Vue d’ensemble

RecruitAI est un assistant intelligent multi-agent conçu pour automatiser la recherche de stages/emplois et la préparation des candidatures.  
Le système est basé sur des **agents spécialisés**, orchestrés dans une pipeline structurée afin d’assurer :

- Une séparation claire des responsabilités  
- Des échanges de données strictement typés (Pydantic)  
- Une réduction maximale des hallucinations  
- Une traçabilité complète du processus  

### Pipeline globale

CandidateProfile
│
▼
Collector ──► OfferRaw[]
│
▼
Analyzer ──► OfferAnalyzed[]
│
▼
Matcher ──► MatchResult[]
│
▼
Writer ──► CV + Lettre (PDF)
│
▼
Tracker ──► Historique des candidatures

---

## 2. Contrats de données (Schemas)

Les agents communiquent exclusivement via des modèles Pydantic :

- `CandidateProfile` : informations candidat + CV brut
- `OfferRaw` : offre collectée brute
- `OfferAnalyzed` : offre enrichie et structurée
- `MatchResult` : score de compatibilité et explications

Ces schémas garantissent la cohérence et la validation des données à chaque étape.

---

## 3. Agent Collector

**Fichier :** `src/agents/collector.py`

### Rôle
Collecter automatiquement des offres pertinentes depuis Google Custom Search API.

### Entrées
- `query` (ex: Data Science)
- `location` (ex: Paris)
- `limit`

### Sortie
- `List[OfferRaw]`

### Responsabilités
- Appel à Google CSE
- Déduplication par URL
- Filtrage des pages non pertinentes :
  - login / captcha
  - forums (Reddit)
  - pages de listings génériques (Glassdoor, LinkedIn search)
  - pages éducatives / catalogues

### Caractéristiques
- Agent **déterministe**
- Aucun usage de LLM
- Objectif : qualité des liens collectés

---

## 4. Agent Analyzer

**Fichier :** `src/agents/analyzer.py`

### Rôle
Transformer une offre brute en données structurées exploitables.

### Entrée
- `OfferRaw`

### Sortie
- `OfferAnalyzed`

### Méthode
- Utilisation d’un LLM (Gemini) pour l’extraction d’informations
- Sortie JSON stricte validée par Pydantic
- Température faible pour limiter la créativité

### Données extraites
- type de contrat
- niveau de séniorité
- compétences techniques
- missions
- exigences
- mots-clés
- résumé court

### Sécurité
- Interdiction d’inventer des informations
- Valeurs manquantes → `unknown` ou listes vides

---

## 5. Agent Matcher

**Fichier :** `src/agents/matcher.py`

### Rôle
Évaluer la compatibilité entre le candidat et chaque offre.

### Entrées
- `CandidateProfile`
- `List[OfferAnalyzed]`

### Sortie
- `List[MatchResult]`

### Approche
- Construction de textes candidat / offre
- Vectorisation (TF-IDF)
- Calcul de similarité cosinus
- Score normalisé entre 0 et 100

### Contenu du résultat
- score global
- raisons du matching
- compétences manquantes
- points forts

### Avantages
- Déterministe
- Explicable
- Robuste pour un MVP académique

---

## 6. Agent Writer

**Fichier :** `src/agents/writer.py`

### Rôle
Générer les documents de candidature ciblés.

### Entrées
- `user_id`
- `CandidateProfile`
- `OfferAnalyzed` (souvent la meilleure offre)

### Sorties
- `data/generated/{user_id}_cv.pdf`
- `data/generated/{user_id}_lettre.pdf`

### Fonctionnement
1. Génération d’un CV complet structuré (JSON) :
   - coordonnées
   - profil
   - compétences
   - expériences
   - projets
   - formation
   - langues
   - certifications
2. Génération d’une lettre de motivation structurée
3. Export en PDF via un module dédié

### Règles anti-hallucination
- Utilisation exclusive des informations présentes dans le CV brut
- Toute information manquante est remplacée par “À compléter”
- Aucun ajout de dates, entreprises ou diplômes inexistants

---

## 7. Agent Tracker

**Fichier :** `src/agents/tracker.py`

### Rôle
Assurer le suivi des candidatures dans le temps.

### Données suivies
- offre
- entreprise
- statut (saved, applied, interview, rejected)
- date
- notes

### Sortie
- fichier persistant `data/tracking.json`

---

## 8. Agent Router

**Fichier :** `src/agents/router.py`

### Rôle
Déterminer l'intention de l'utilisateur et diriger la requête vers le bon agent ou workflow.

### Intentions supportées
- `job_pipeline` : Recherche et analyse d'offres d'emploi.
- `rag_agent` : Questions sur le CV ou le profil de l'utilisateur.
- `stats_agent` : Requêtes statistiques sur les offres d'emploi collectées.
- `general_chat` : Conversation générale ou aide.

### Méthode
- Utilisation de Gemini-Flash avec un prompt structuré.
- Fallback par expressions régulières si le LLM échoue à produire un JSON valide.

---

## 9. Agent RAG (Retrieval-Augmented Generation)

**Fichier :** `src/agents/rag_agent.py`

### Rôle
Répondre à des questions spécifiques sur le profil du candidat en utilisant une base de connaissances vectorielle.

### Stratégie de Chunking
Pour assurer une récupération précise des informations du CV, nous utilisons le **`RecursiveCharacterTextSplitter`** :
- **Chunk Size :** 1000 caractères.
- **Overlap :** 100 caractères.
- **Rationale :** Ce splitter préserve mieux la structure sémantique (paragraphes, listes à puces) que les splitters par taille fixe ou purement sémantiques qui peuvent perdre le contexte des sections de CV.

### Stockage Vectoriel
- **Moteur :** FAISS (In-Memory).
- **Embeddings :** `models/embedding-001` (Google).
- **Emplacement :** `data/faiss_index/`. Ce dossier contient l'index binaire et les métadonnées permettant des recherches de similarité ultra-rapides sans base de données externe.

---

## 10. Agent Stats

**Fichier :** `src/agents/stats_agent.py`

### Rôle
Effectuer des analyses de données sur les offres d'emploi analysées (`job_offers_analyzed.json`).

### Fonctionnement
- Utilise **Pandas** pour charger les données structurées.
- Exploite le `create_pandas_dataframe_agent` de LangChain.
- Permet de répondre à des questions comme "Quel est le salaire moyen ?", "Combien d'offres en télétravail ?", etc.

---

## 11. Orchestration (LangGraph)

**Fichier :** `src/graph/build_graph.py`

### Objectif
Relier les agents dans un workflow explicite et contrôlé.

### État partagé (`RecruitAIState`)
- `messages` : Historique de la conversation.
- `candidate` : Profil structuré du candidat.
- `query` : Requête de l'utilisateur.
- `job_offers` : Liste des offres brutes/analysées.
- `matches` : Résultats du matching.

---

## 12. Conclusion

RecruitAI implémente une architecture multi-agent moderne et robuste :
- **Hybride :** Combine des agents LLM (Router, Analyzer, RAG) et des agents déterministes (Collector, Matcher).
- **RAG Optimisé :** Utilise un chunking intelligent pour le traitement de documents RH.
- **Data-Driven :** Intègre une capacité d'analyse statistique en temps réel sur le marché de l'emploi.


