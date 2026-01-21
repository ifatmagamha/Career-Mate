# Schemas – RecruitAI

Ce dossier définit **les contrats de données officiels** du projet RecruitAI.  
Tous les agents (Collector, Analyzer, Matcher, Writer, Tracker) ainsi que le LangGraph
s’appuient exclusivement sur ces schémas.

👉 **Règle d’or : ces schémas sont figés après l’étape 0.**  
Toute modification doit être justifiée, car elle impacte l’ensemble du pipeline.

---

## 🎯 Objectifs des schémas

- Garantir une **communication fiable** entre les agents
- Éviter les ambiguïtés et les hallucinations côté LLM
- Faciliter la sérialisation (JSON) et la persistance (fichiers, DB)
- Rendre le projet **lisible et évaluable** académiquement

Les schémas sont implémentés avec **Pydantic v2**.

---

## 📄 `job_offer.py`

Ce fichier décrit le cycle de vie d’une offre d’emploi dans RecruitAI.

### 1️⃣ `OfferRaw`
Représente une **offre brute**, telle qu’elle est collectée depuis une source externe
(ex: Google Custom Search).

**Utilisé par :**
- Collector agent
- Point d’entrée du pipeline

**Champs principaux :**
- `title` : titre de l’offre
- `company` : entreprise (si détectable)
- `location` : localisation
- `description` : extrait textuel brut
- `url` : URL canonique de l’offre (clé d’identification)

👉 Aucun traitement sémantique n’est fait à ce stade.

---

### 2️⃣ `OfferAnalyzed`
Représente une **offre analysée et structurée** par l’agent Analyzer (LLM).

**Utilisé par :**
- Analyzer agent (output)
- Matcher agent
- Writer agent

**Caractéristiques clés :**
- Structure **JSON stricte**
- Champs normalisés (skills, missions, requirements)
- Typage contrôlé (`contract_type`, `seniority`)
- Pensé pour le **matching automatique**

**Principe anti-hallucination :**
L’Analyzer est contraint à produire uniquement ce schéma (pas de texte libre).

---

### 3️⃣ `MatchResult`
Résultat du matching entre un **candidat** et une **offre analysée**.

**Utilisé par :**
- Matcher agent
- Tracker agent
- Dashboard Streamlit

**Contenu :**
- `score` (0–100) : score global de compatibilité
- `reasons` : explication du score
- `missing_skills` : écarts à combler
- `strong_points` : adéquation forte profil ↔ offre

👉 Le score est **reproductible** (partie rule-based) et **explicable** (partie LLM).

---

## 📄 `candidate.py`

Ce fichier définit le **profil candidat minimal** pour le MVP.

### `CandidateProfile`

Représente le candidat tel qu’il est fourni au système.

**Champ central :**
- `cv_text` (obligatoire)  
  → CV en texte brut (copié-collé ou extrait PDF)

**Champs optionnels :**
- informations de contact
- rôles cibles (`target_roles`)
- mots-clés préférés (`target_keywords`)

---

### 🔒 Principe clé (anti-hallucination)

> Le Writer Agent n’a **pas le droit d’inventer** des expériences, compétences ou diplômes.  
> Il doit se baser **exclusivement** sur `cv_text`.

Ce schéma garantit cette contrainte.

---

## 🧠 Pourquoi ce design ?

- **Séparation claire des responsabilités**
- Pipeline déterministe et traçable
- Facilite l’évaluation académique (architecture, IA, agents)
- Compatible avec LangGraph, RAG et dashboards

---


- `schemas/` 
- Tous les agents doivent respecter ces modèles
- Toute évolution future passe par une extension contrôlée

---

📅 Étape du projet : **Étape 0 – Verrouillage des schémas**
