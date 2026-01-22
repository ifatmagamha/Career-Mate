# RecruitAI — Architecture du Système

## 1. Introduction

RecruitAI est un assistant intelligent multi-agent destiné à automatiser et optimiser le processus de recherche de stages/emplois et de candidature.  
L’architecture du système est conçue pour être :

- **Modulaire** : chaque composant a un rôle précis
- **Scalable** : ajout facile de nouveaux agents ou sources
- **Robuste** : validation systématique des données
- **Explicable** : décisions compréhensibles (matching déterministe)

L’architecture repose sur une **pipeline agentique** orchestrée (via LangGraph ou une orchestration équivalente).

---

## 2. Vue globale de l’architecture

### Diagramme logique

┌────────────────────┐
│ Interface Utilisateur │
│ (Streamlit App) │
└─────────┬──────────┘
│
▼
┌────────────────────┐
│ Candidate Profile │
│ (CV, objectifs) │
└─────────┬──────────┘
│
▼
┌────────────────────┐
│ Collector Agent │
│ (Google CSE) │
└─────────┬──────────┘
▼
┌────────────────────┐
│ Analyzer Agent │
│ (LLM - Gemini) │
└─────────┬──────────┘
▼
┌────────────────────┐
│ Matcher Agent │
│ (Cosine Similarity)│
└─────────┬──────────┘
▼
┌────────────────────┐
│ Writer Agent │
│ (CV & Lettre PDF) │
└─────────┬──────────┘
▼
┌────────────────────┐
│ Tracker Agent │
│ (Historique) │
└────────────────────┘

---

## 3. Découpage par couches

### 3.1 Interface (UI Layer)

**Technologie :** Streamlit  
**Dossier :** `app/`

Responsabilités :
- Authentification utilisateur
- Saisie du profil candidat (CV texte, GitHub, préférences)
- Interaction conversationnelle avec un LLM
- Lancement des workflows (recherche, génération)
- Téléchargement des fichiers PDF
- Visualisation des résultats et du suivi

---

### 3.2 Couche Agents (Business Logic)

**Dossier :** `src/agents/`

Chaque agent :
- a une responsabilité unique
- communique via des schémas Pydantic
- peut être testé indépendamment

Agents principaux :
- `collector.py`
- `analyzer.py`
- `matcher.py`
- `writer.py`
- `tracker.py`

---

### 3.3 Couche Orchestration

**Dossier :** `src/graph/`

Responsabilités :
- Définir l’ordre d’exécution des agents
- Gérer l’état partagé (state)
- Garantir une pipeline déterministe

Approche :
- LangGraph (ou équivalent)
- Chaque nœud = un agent
- Transitions explicites

---

### 3.4 Couche Données & Schémas

**Dossier :** `src/schemas/`

Rôle :
- Définir les contrats de données
- Valider toutes les entrées/sorties
- Réduire les erreurs et hallucinations

Schémas clés :
- `CandidateProfile`
- `OfferRaw`
- `OfferAnalyzed`
- `MatchResult`

---

### 3.5 Couche LLM

**Dossier :** `src/llm/`

Rôle :
- Abstraction du fournisseur LLM (Gemini)
- Centralisation de la configuration
- Gestion des erreurs (429, fallback de modèle)

Utilisations :
- Extraction d’informations (Analyzer)
- Génération de documents (Writer)
- Interaction conversationnelle (Chat UI)

---

### 3.6 Couche Export & Persistance

**Dossiers :**
- `src/export/`
- `data/`

Fonctions :
- Génération de PDF (CV, lettre)
- Sauvegarde des résultats intermédiaires :
  - offres collectées
  - offres analysées
  - scores de matching
- Suivi des candidatures (`tracking.json`)

---

## 4. Flux de données détaillé

### Étape 1 — Profil candidat
- L’utilisateur renseigne ses informations
- Le CV est stocké sous forme de texte brut
- Validation via `CandidateProfile`

### Étape 2 — Collecte
- Appel à Google CSE
- Filtrage des résultats
- Création d’objets `OfferRaw`

### Étape 3 — Analyse
- Le LLM extrait les informations clés
- Génération d’`OfferAnalyzed`
- Données normalisées et validées

### Étape 4 — Matching
- Similarité cosinus entre profil et offre
- Score 0–100
- Génération de `MatchResult`

### Étape 5 — Génération de documents
- Sélection de la meilleure offre
- Génération d’un CV complet ciblé
- Génération d’une lettre de motivation
- Export PDF

### Étape 6 — Tracking
- Enregistrement de la candidature
- Suivi de l’évolution du statut

---

## 5. Choix architecturaux clés

### Pourquoi une architecture multi-agent ?
- Modularité
- Testabilité
- Facilité d’évolution
- Alignement avec les systèmes agentiques (IAG)

### Pourquoi limiter l’usage du LLM ?
- Réduction des hallucinations
- Coût maîtrisé
- Comportement plus prévisible

### Pourquoi un matching déterministe ?
- Scores explicables
- Acceptable académiquement
- Complémentaire à l’IA générative

---

## 6. Sécurité & Robustesse

- Validation Pydantic partout
- Valeurs par défaut explicites
- Fallbacks en cas d’échec LLM
- Journaux (`logging`) pour le debug

---

## 7. Extensibilité future

L’architecture permet facilement :
- Ajout de nouvelles sources (LinkedIn, Indeed scraping)
- Intégration RAG + vector store
- Analyse automatique de GitHub
- Envoi automatique des candidatures
- Multi-langue (FR / EN)
- Déploiement cloud

---

## 8. Conclusion

L’architecture de RecruitAI illustre une approche réaliste et académique des systèmes multi-agents :

- Orchestration claire
- Agents spécialisés
- Usage raisonné des LLMs
- Application finale exploitable

