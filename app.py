import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import math
import hashlib

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Community Directory", page_icon="📂")

# --- Add API KEY ---
API_KEY = "AIzaSyDHN8h0W5ZsF8ywgLZXUiwL0cz9k-b0WkE"  # Replace with your actual key
if API_KEY == "YOUR_GEMINI_API_KEY_HERE":
    st.warning("⚠️ Please replace 'YOUR_GEMINI_API_KEY_HERE' with your actual Gemini key")
else:
    genai.configure(api_key=API_KEY)

# --- CSS ---
def load_custom_css():
    st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    div[data-testid="stTextInput"] input { border-radius: 25px; border: 1px solid #dfe1e5; padding: 10px 20px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; background: white; border: 1px solid #f0f2f6; transition: all 0.2s; }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); border-color: #FF4B4B; }
    img { border-radius: 8px; object-fit: cover; }
    .data-bubble { background-color: #f8f9fa; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #FF4B4B; }
    .data-label { font-weight: bold; font-size: 0.8rem; color: #888; }
    .data-value { color: #111; font-size: 0.95rem; }
    </style>
    """, unsafe_allow_html=True)
load_custom_css()

# --- Helper Functions ---
def get_file_hash(file):
    file.seek(0)
    bytes_data = file.read()
    file.seek(0)
    return hashlib.md5(bytes_data).hexdigest()

@st.cache_data(show_spinner=False)
def get_ai_column_map(columns_list):
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        prompt = f"""
        Map headers to short, Title Case keys (max 3 words). Return JSON.
        Headers: {columns_list}
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json','').replace('```','').strip()
        return json.loads(clean_text)
    except Exception:
        return {col: col for col in columns_list}

@st.cache_data(show_spinner=False)
def load_and_clean_data_cached(file_hash, file):
    df = pd.read_csv(file)
    
    # AI Mapping
    mapping = get_ai_column_map(df.columns.tolist())
    df = df.rename(columns=mapping)

    # Identify key columns
    cols_lower = [c.lower() for c in df.columns]
    try: name_col = df.columns[[i for i, c in enumerate(cols_lower) if 'name' in c][0]]
    except: name_col = df.columns[0]
    try: img_col = df.columns[[i for i, c in enumerate(cols_lower) if 'photo' in c or 'image' in c or 'pic' in c][0]]
    except: img_col = None

    # Clean image links
    if img_col:
        def clean_link(link):
            if pd.isna(link) or not isinstance(link, str): return None
            if "drive.google.com" in link:
                if "id=" in link: return f"https://drive.google.com/thumbnail?id={link.split('id=')[-1].split('&')[0]}&sz=w1000"
                if "/d/" in link: return f"https://drive.google.com/thumbnail?id={link.split('/d/')[-1].split('/')[0]}&sz=w1000"
            return link
        df[img_col] = df[img_col].apply(clean_link)

    # Lazy search index: only text columns
    text_cols = [c for c in df.columns if c not in [img_col]]
    df['ALL_TEXT_SEARCH'] = df[text_cols].astype(str).agg(' '.join, axis=1).str.lower()

    return df, name_col, img_col

# --- Profile Dialog ---
@st.dialog("Profile Details", width="large")
def show_profile(row, name_col, img_col):
    c1, c2 = st.columns([1, 2])
    with c1:
        if row.get(img_col): st.image(row[img_col], use_container_width=True)
        else: st.markdown("### 👤 No Photo")
    with c2:
        st.markdown(f"## {row.get(name_col)}")
    st.divider()
    for col, val in row.items():
        if col in [name_col, img_col, 'ALL_TEXT_SEARCH']: continue
        display_val = str(val).replace(";", "\n• ") if (pd.notna(val) and str(val).strip() != "") else "Not Provided"
        st.markdown(f"<div class='data-bubble'><div class='data-label'>{col}</div><div class='data-value'>{display_val}</div></div>", unsafe_allow_html=True)

# --- MAIN APP ---
st.title("📂 Community Directory")
uploaded_file = st.file_uploader("Upload CSV", type=['csv'])

if uploaded_file:
    file_hash = get_file_hash(uploaded_file)
    if 'df' not in st.session_state or st.session_state.get('file_hash') != file_hash:
        with st.spinner("Processing data..."):
            df, name_col, img_col = load_and_clean_data_cached(file_hash, uploaded_file)
        st.session_state.df = df
        st.session_state.name_col = name_col
        st.session_state.img_col = img_col
        st.session_state.file_hash = file_hash

    df = st.session_state.df
    name_col = st.session_state.name_col
    img_col = st.session_state.img_col

    # Persist search query
    if 'search_query' not in st.session_state: st.session_state.search_query = ""
    st.session_state.search_query = st.text_input("🔍 Search...", value=st.session_state.search_query).lower()

    # Filter
    if st.session_state.search_query:
        display_df = df[df['ALL_TEXT_SEARCH'].str.contains(st.session_state.search_query, na=False)]
    else:
        display_df = df

    # Pagination
    ITEMS_PER_PAGE = 12
    total_items = len(display_df)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    if 'current_page' not in st.session_state: st.session_state.current_page = 1

    c1, c2, c3 = st.columns([2,6,2])
    with c1:
        if st.button("Previous") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
            st.rerun()
    with c2:
        st.caption(f"Showing {total_items} members | Page {st.session_state.current_page} of {max(1, total_pages)}")
    with c3:
        if st.button("Next") and st.session_state.current_page < total_pages:
            st.session_state.current_page += 1
            st.rerun()

    # Slice for lazy loading
    start_idx = (st.session_state.current_page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_df = display_df.iloc[start_idx:end_idx]

    # Grid display
    st.divider()
    cols = st.columns(4)
    for idx, (index, row) in enumerate(page_df.iterrows()):
        with cols[idx % 4]:
            if row.get(img_col): st.image(row[img_col], use_container_width=True)
            else: st.markdown('<div style="height:150px; background:#eee; border-radius:8px;"></div>', unsafe_allow_html=True)
            st.subheader(row.get(name_col, "Unknown"))
            if st.button("View Profile", key=f"btn_{index}", use_container_width=True):
                show_profile(row, name_col, img_col)
