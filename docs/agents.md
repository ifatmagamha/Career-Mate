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

## 8. Orchestration (LangGraph)

**Fichier :** `src/graph/build_graph.py`

### Objectif
Relier les agents dans un workflow explicite et contrôlé.

### État partagé
- profil candidat
- offres collectées
- offres analysées
- résultats de matching
- documents générés

### Avantages
- Pipeline lisible
- Débogage facilité
- Valeur académique forte (systèmes agentiques)

---

## 9. Fichiers générés

Après exécution complète :

- `data/job_offers_raw.json`
- `data/job_offers_analyzed.json`
- `data/matches.json`
- `data/generated/{user_id}_cv.pdf`
- `data/generated/{user_id}_lettre.pdf`
- `data/tracking.json`

---

## 10. Conclusion

RecruitAI implémente une architecture multi-agent réaliste et maîtrisée :
- LLM utilisé uniquement là où il apporte de la valeur
- Matching déterministe et explicable
- Documents générés automatiquement et prêts à l’envoi
- Application exploitable via une interface Streamlit


