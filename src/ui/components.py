import streamlit as st

def render_job_card(job: dict):
    """
    Renders a job offer as a stylish card using HTML/CSS.
    Matches the Career Mate aesthetic: Clean white/dark card, tags, and clear actions.
    """
    # Extract fields with safe defaults
    title = job.get("title", "Untitled Position")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Remote/Unspecified")
    url = job.get("url", "#")
    salary = job.get("salary") or "Competitive" 
    contract = job.get("contract_type", "Full-time")
    
    # Handle tags
    skills = job.get("skills", [])
    if isinstance(skills, list):
         # Limit to 5 skills to avoid clutter
        tags_html = "".join([f'<span style="background-color: #312e81; color: #e0e7ff; padding: 4px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; margin-right: 6px; margin-bottom: 4px; display: inline-block;">{s}</span>' for s in skills[:5]])
    else:
        tags_html = ""

    # Card HTML
    card_html = f"""
    <div style="
        border: 1px solid #374151; 
        border-radius: 16px; 
        padding: 20px; 
        margin-bottom: 16px; 
        background-color: #111827; 
        color: #f9fafb; 
        transition: transform 0.2s;
    ">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div style="flex-grow: 1;">
                <h4 style="margin: 0 0 6px 0; font-size: 1.15rem; font-weight: 700; color: #818cf8;">{title}</h4>
                <p style="margin: 0 0 12px 0; color: #9ca3af; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;">
                    <span>🏢 {company}</span>
                    <span style="color: #4b5563;">|</span>
                    <span>📍 {location}</span>
                </p>
            </div>
            <div style="flex-shrink: 0; margin-left: 16px;">
                <a href="{url}" target="_blank" style="
                    background-color: #4f46e5;
                    color: white; 
                    text-decoration: none; 
                    padding: 8px 16px; 
                    border-radius: 8px; 
                    font-size: 0.9rem; 
                    font-weight: 600;
                    display: inline-block;
                    text-align: center;
                    box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);
                ">Apply ↗</a>
            </div>
        </div>
        
        <div style="margin: 8px 0 16px 0; display: flex; align-items: center; gap: 12px; font-size: 0.85rem; color: #d1d5db;">
             <span style="background: #1f2937; padding: 4px 8px; border-radius: 6px;">💰 {salary}</span>
             <span style="background: #1f2937; padding: 4px 8px; border-radius: 6px;">🕒 {contract}</span>
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 4px;">
            {tags_html}
        </div>
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

def render_kanban_column(title: str, jobs: list, status_key: str, color: str = "#4f46e5"):
    """
    Renders a column for the Kanban board with a modern header and card counting.
    """
    count = len(jobs)
    
    # Column Header
    st.markdown(f"""
    <div style="
        border-top: 4px solid {color}; 
        padding-top: 12px; 
        margin-bottom: 16px; 
        display: flex; 
        align-items: center; 
        justify-content: space-between;
    ">
        <h3 style="margin: 0; font-size: 0.95rem; font-weight: 700; color: #e5e7eb; text-transform: uppercase; letter-spacing: 0.05em;">{title}</h3>
        <span style="
            background-color: {color}20; 
            color: {color}; 
            border-radius: 999px; 
            padding: 2px 8px; 
            font-size: 0.8rem; 
            font-weight: 700;
        ">{count}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Render Cards in Column
    for job in jobs:
        with st.container():
            st.markdown(f"""
            <div style="
                padding: 14px; 
                background-color: #1f2937; 
                border-radius: 10px; 
                margin-bottom: 12px;
                border: 1px solid #374151;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            ">
                <div style="font-weight: 600; font-size: 0.95rem; color: #f3f4f6; margin-bottom: 4px;">{job.get('title', 'Untitled')}</div>
                <div style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 8px;">{job.get('company', 'Unknown')}</div>
                
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #374151; padding-top: 8px; margin-top: 8px;">
                    <span style="font-size: 0.75rem; color: #6b7280;">{job.get('updated_at', 'Recently')[:10]}</span>
                    <a href="{job.get('url', '#')}" target="_blank" style="text-decoration: none; font-size: 0.8rem; color: #818cf8;">View ↗</a>
                </div>
            </div>
            """, unsafe_allow_html=True)
