import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import math

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Community Directory", page_icon="📂")

# --- Add API KEY ---
API_KEY = "AIzaSyDHN8h0W5ZsF8ywgLZXUiwL0cz9k-b0WkE" 

# Configure AI
if API_KEY == "YOUR_GEMINI_API_KEY_HERE":
    st.warning("⚠️ Please replace 'YOUR_GEMINI_API_KEY_HERE' in the code with your actual key from aistudio.google.com")
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

# --- ⚡ OPTIMIZATION 1: CACHING THE AI CALL ---
# This function will now ONLY run when the 'columns_tuple' changes.
# If you upload the same file, it loads instantly from cache.
@st.cache_data(show_spinner=False) 
def get_ai_column_map(columns_list):
    try:
        # Using your preferred model
        model = genai.GenerativeModel('gemini-2.5-pro') 
        prompt = f"""
        Map headers to short, Title Case keys (max 3 words). Return JSON.
        "Upload a clear profile photo..." -> "Photo"
        "Your full name?" -> "Name"
        Headers: {columns_list}
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception:
        return {col: col for col in columns_list}

# --- ⚡ OPTIMIZATION 2: PRE-PROCESSING DATA ---
# We clean links and create a search index ONCE during load, not during render.
@st.cache_data(show_spinner=False)
def load_and_clean_data(file):
    df = pd.read_csv(file)
    
    # 1. Run AI Mapping
    raw_cols = df.columns.tolist()
    mapping = get_ai_column_map(raw_cols) # This is cached now!
    df = df.rename(columns=mapping)
    
    # 2. Identify Key Columns
    cols_lower = [c.lower() for c in df.columns]
    try:
        name_col = df.columns[[i for i, c in enumerate(cols_lower) if 'name' in c][0]]
    except:
        name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
    try:
        img_col = df.columns[[i for i, c in enumerate(cols_lower) if 'photo' in c or 'image' in c or 'pic' in c][0]]
    except:
        img_col = None

    # 3. Fix Images in Bulk (Faster than doing it row-by-row later)
    if img_col:
        def clean_link(link):
            if pd.isna(link) or not isinstance(link, str): return None
            if "drive.google.com" in link:
                if "id=" in link: return f"https://drive.google.com/thumbnail?id={link.split('id=')[-1].split('&')[0]}&sz=w1000"
                if "/d/" in link: return f"https://drive.google.com/thumbnail?id={link.split('/d/')[-1].split('/')[0]}&sz=w1000"
            return link
        df[img_col] = df[img_col].apply(clean_link)

    # 4. Create "Search Index" (The Speed Secret)
    # Combine all text columns into one lowercase string for instant searching
    df['ALL_TEXT_SEARCH'] = df.astype(str).apply(lambda x: ' '.join(x), axis=1).str.lower()
    
    return df, name_col, img_col

# --- UI LOGIC ---

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

st.title("⚡ Fast Community Directory")
uploaded_file = st.file_uploader("Upload CSV", type=['csv'])

if uploaded_file:
    # Load Data (Cached)
    with st.spinner("Processing data..."):
        df, name_col, img_col = load_and_clean_data(uploaded_file)

    # Search
    search_query = st.text_input("🔍 Search...", placeholder="Type a name, skill, or interest...").lower()

    # Filter (Using the fast index)
    if search_query:
        display_df = df[df['ALL_TEXT_SEARCH'].str.contains(search_query, na=False)]
    else:
        display_df = df

    # --- ⚡ OPTIMIZATION 3: PAGINATION ---
    ITEMS_PER_PAGE = 12
    
    # Calculate pages
    total_items = len(display_df)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    
    # Initialize page state
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    
    # Controls
    c1, c2, c3 = st.columns([2, 6, 2])
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

    # Slice Data for current page
    start_idx = (st.session_state.current_page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_df = display_df.iloc[start_idx:end_idx]

    # Grid Display
    st.divider()
    cols = st.columns(4)
    for idx, (index, row) in enumerate(page_df.iterrows()):
        with cols[idx % 4]:
            with st.container(border=True):
                if row.get(img_col): st.image(row[img_col], use_container_width=True)
                else: st.markdown('<div style="height:150px; background:#eee; border-radius:8px;"></div>', unsafe_allow_html=True)
                st.subheader(row.get(name_col, "Unknown"))
                if st.button("View Profile", key=f"btn_{index}", use_container_width=True):
                    show_profile(row, name_col, img_col)
