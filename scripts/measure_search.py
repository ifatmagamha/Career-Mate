"""
Measure keyword vs semantic vs hybrid offer search on a small labeled FR/EN set (real embeddings),
and the cosine distribution of relevant vs irrelevant pairs.

Re-run after changing the embedding model, then set min_similarity in [roles.embed] of config/models.toml:
  uv run python scripts/measure_search.py
Uses a throwaway Postgres schema (your data is not touched); ~11 embedding calls.
"""
import sys
import uuid
from statistics import mean, median

sys.path.insert(0, ".")

import src.storage.offer_search as S
from src.storage import db

OFFERS = [
    {"title": "Data Engineer", "company": "Doctolib", "location": "Paris", "skills": ["Airflow", "dbt", "SQL"],
     "summary": "Build and maintain batch data pipelines feeding the analytics warehouse."},
    {"title": "Ingénieur données", "company": "BNP Paribas", "location": "Paris", "skills": ["Spark", "SQL", "Python"],
     "summary": "Concevoir des pipelines de données et industrialiser les flux pour la banque de détail."},
    {"title": "Machine Learning Engineer Intern", "company": "Alan", "location": "Lyon", "skills": ["PyTorch", "Python"],
     "summary": "Train and deploy models that help members understand their health insurance."},
    {"title": "Stage Data Scientist", "company": "Qonto", "location": "Paris", "skills": ["Python", "statistiques"],
     "summary": "Stage en apprentissage automatique : modèles de détection de fraude sur les transactions."},
    {"title": "Account Executive", "company": "Doctolib", "location": "Annecy", "skills": ["Salesforce", "CRM"],
     "summary": "Prospect healthcare professionals and close new subscriptions in the field."},
    {"title": "Business Developer", "company": "Swile", "location": "Montpellier", "skills": ["Prospection", "Négociation"],
     "summary": "Développement commercial B2B : prospecter des entreprises et signer de nouveaux clients."},
    {"title": "Product Designer", "company": "Back Market", "location": "Paris", "skills": ["Figma", "UX research"],
     "summary": "Design end-to-end user experiences for the buyer journey."},
    {"title": "Frontend Developer", "company": "Algolia", "location": "Remote", "remote_policy": "remote",
     "skills": ["React", "TypeScript"], "summary": "Build the dashboard UI used by thousands of developers."},
    {"title": "DevOps Engineer", "company": "Mistral", "location": "Remote", "remote_policy": "remote",
     "skills": ["Kubernetes", "Terraform", "AWS"], "summary": "Run and automate the cloud infrastructure behind model serving."},
    {"title": "HR Business Partner", "company": "Decathlon", "location": "Lille", "skills": ["Recrutement", "Droit social"],
     "summary": "Accompagner les managers sur le recrutement, la gestion des talents et les relations sociales."},
]
QUERIES = {
    "data pipelines": {0, 1},
    "ingénieur données": {0, 1},
    "apprentissage automatique": {2, 3},
    "machine learning internship": {2, 3},
    "vente B2B": {4, 5},
    "sales jobs": {4, 5},
    "UX design": {6},
    "remote cloud infrastructure": {8},
    "react developer": {7},
    "recrutement RH": {9},
}



def pct(xs, p):
    """p-th percentile (nearest rank)."""
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))]


U = str(uuid.uuid4())
with db.temp_schema() as conn:
    ids = [db.insert_offer(conn, U, o)["id"] for o in OFFERS]
    idx = {oid: i for i, oid in enumerate(ids)}
    model = S._embed_model()
    print("embedded:", S.ensure_embeddings(conn, U, model=model), "offers with", model)

    rel_sims, irr_sims = [], []
    keep_k, keep_min = S.DENSE_TOP_K, S.MIN_SIMILARITY
    S.DENSE_TOP_K, S.MIN_SIMILARITY = 100, -1.0  # raw cosines for every offer
    raw = {q: dict(S.semantic_ranking(conn, U, q, ids, embed=S._default_embed, model=model)) for q in QUERIES}
    S.DENSE_TOP_K, S.MIN_SIMILARITY = keep_k, keep_min
    for q, rel in QUERIES.items():
        for oid, sim in raw[q].items():
            (rel_sims if idx[oid] in rel else irr_sims).append(sim)
    print(f"cosine relevant   min {min(rel_sims):.3f}  p10 {pct(rel_sims, 10):.3f}  median {median(rel_sims):.3f}")
    print(f"cosine irrelevant max {max(irr_sims):.3f}  p90 {pct(irr_sims, 90):.3f}  median {median(irr_sims):.3f}")
    for thr in (0.55, 0.6, 0.62, 0.65, 0.68, 0.7):
        tp = sum(x >= thr for x in rel_sims); fp = sum(x >= thr for x in irr_sims)
        print(f"  threshold {thr:.2f}: keeps {tp}/{len(rel_sims)} relevant, {fp}/{len(irr_sims)} irrelevant")

    def evaluate(floor, margin):
        print(f"\nfloor {floor}  margin {margin}")
        for mode in ("keyword", "semantic", "hybrid"):
            recall3, prec, mrr = [], [], []
            for q, rel in QUERIES.items():
                if mode == "keyword":
                    res = [o["id"] for o in db.query_offers(conn, U, {"q": q, "sort": "relevance"})]
                else:
                    dense = [oid for oid, _ in S.semantic_ranking(conn, U, q, ids, embed=S._default_embed, model=model,
                                                                  min_similarity=floor, margin=margin)]
                    if mode == "semantic":
                        res = dense
                    else:
                        kw = [o["id"] for o in db.query_offers(conn, U, {"q": q, "sort": "relevance"})]
                        sc = S.rrf(kw, dense)
                        res = sorted(sc, key=lambda i: -sc[i])
                got = [idx[r] for r in res]
                recall3.append(len(set(got[:3]) & rel) / len(rel))
                prec.append(len(set(got) & rel) / len(got) if got else 0.0)
                mrr.append(next((1 / (i + 1) for i, g in enumerate(got) if g in rel), 0.0))
            print(f"  {mode:<8} recall@3 {mean(recall3):.2f}  precision {mean(prec):.2f}  MRR {mean(mrr):.2f}")

    for floor, margin in ((0.55, None), (0.45, 0.03), (0.45, 0.05), (0.45, 0.08), (0.5, 0.05)):
        evaluate(floor, margin)
