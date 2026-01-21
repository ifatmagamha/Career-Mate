import streamlit as st
import pandas as pd

st.set_page_config(page_title="Matching", layout="wide")
st.title("2) Matching")

result = st.session_state.get("last_result")
if not result:
    st.warning("Va d’abord sur 'Collecte & Analyse' et lance le pipeline.")
    st.stop()

matches = result.get("matches", [])
offers = {o.id: o for o in result.get("offers_parsed", [])}

df = pd.DataFrame([{
    "job_id": m.job_id,
    "score": m.score,
    "matched_skills": ", ".join(m.matched_skills[:10]),
    "missing_skills": ", ".join(m.missing_skills[:10]),
    "title": offers.get(m.job_id).title if offers.get(m.job_id) else "",
    "company": offers.get(m.job_id).company if offers.get(m.job_id) else "",
} for m in matches]).sort_values("score", ascending=False)

st.dataframe(df, use_container_width=True)

st.subheader("Détail d'une offre")
selected = st.selectbox("Choisir une offre (job_id)", df["job_id"].tolist())
m = next(x for x in matches if x.job_id == selected)
o = offers.get(selected)

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown(f"### {o.title if o else selected}")
    st.write("Entreprise:", o.company if o else None)
    st.write("Localisation:", o.location if o else None)
    st.write("Score:", m.score)
    st.write("Reasons:", m.reasons)

    st.markdown("**Missions**")
    st.write(o.missions[:15] if o else [])
    st.markdown("**Requirements**")
    st.write(o.requirements[:15] if o else [])
with col2:
    st.markdown("**Matched skills**")
    st.write(m.matched_skills)
    st.markdown("**Missing skills**")
    st.write(m.missing_skills)
    st.markdown("**Recommendations**")
    st.write(m.recommendations)
