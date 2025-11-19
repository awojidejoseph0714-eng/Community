import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import time

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(layout="wide", page_title="Community Directory", page_icon="📂")

# !!! REPLACE WITH YOUR KEY OR USE st.secrets !!!
# If deploying to Streamlit Cloud, it is safer to put this in "Secrets" settings
# and access it via st.secrets["GEMINI_API_KEY"]
API_KEY = "AIzaSyDHN8h0W5ZsF8ywgLZXUiwL0cz9k-b0WkE" 

# Configure AI
if API_KEY == "YOUR_GEMINI_API_KEY_HERE":
    st.warning("⚠️ Please replace 'YOUR_GEMINI_API_KEY_HERE' in the code with your actual key from aistudio.google.com")
else:
    genai.configure(api_key=API_KEY)


# --- 2. DESIGN & CSS ---
def load_custom_css():
    st.markdown("""
        <style>
        /* Global Font & Spacing */
        .block-container { padding-top: 2rem; padding-bottom: 3rem; }
        
        /* Search Bar Styling */
        div[data-testid="stTextInput"] input {
            border-radius: 25px;
            border: 1px solid #dfe1e5;
            padding: 10px 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        /* Card Container Styling */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border: 1px solid #f0f2f6;
            transition: all 0.2s ease-in-out;
        }
        
        /* Card Hover Effect */
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            border-color: #FF4B4B;
        }

        /* Profile Images */
        img { border-radius: 8px; object-fit: cover; }
        
        /* Text Styling */
        h3 { font-size: 1.1rem !important; font-weight: 700 !important; margin-bottom: 0px; }
        p { font-size: 0.9rem; color: #555; }
        
        /* Popup Data Bubbles */
        .data-bubble {
            background-color: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 4px solid #FF4B4B;
        }
        .data-label { font-weight: bold; font-size: 0.85rem; color: #888; margin-bottom: 2px; }
        .data-value { color: #111; font-size: 1rem; }
        </style>
    """, unsafe_allow_html=True)

load_custom_css()


# --- 3. AI & DATA FUNCTIONS ---

def get_ai_column_map(columns_list):
    """Uses Gemini to shorten column names to standard keys."""
    try:
        # CHANGED: Try 'gemini-pro' which is the most widely available model
        model = genai.GenerativeModel('gemini-2.5-flash') 

        prompt = f"""
        I have a list of column headers from a Google Form. 
        Map EVERY single header to a short, human-readable, Title Case name (max 3 words).
        
        Rules:
        1. Return ONLY valid JSON. No markdown formatting.
        2. Keys = Original Headers, Values = New Short Name.
        3. "Upload a clear profile photo..." -> "Photo"
        4. "Your full name?" -> "Name"
        5. "Timestamp" -> "Submitted"

        Headers: {columns_list}
        """
        response = model.generate_content(prompt)
        # Clean string to ensure it's pure JSON
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"AI Mapping Failed: {e}. Using original names.")
        # Fallback: Map columns to themselves
        return {col: col for col in columns_list}

def fix_image_link(link):
    """Converts Google Drive links to viewable image URLs."""
    if pd.isna(link) or not isinstance(link, str):
        return None
    
    if "drive.google.com" in link:
        # Extract ID
        if "id=" in link:
            file_id = link.split('id=')[-1].split('&')[0]
        elif "/d/" in link:
            file_id = link.split('/d/')[-1].split('/')[0]
        else:
            return None
        # Return embeddable URL
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
    
    return link # Return as-is if it's already a direct link

# --- 4. THE POPUP (DETAIL VIEW) ---

@st.dialog("Profile Details", width="large")
def show_profile(row, name_col, img_col):
    # Header Section
    c1, c2 = st.columns([1, 2])
    with c1:
        img_url = fix_image_link(row.get(img_col))
        if img_url:
            st.image(img_url, use_container_width=True)
        else:
            st.markdown("### 👤 No Photo")
    
    with c2:
        st.markdown(f"## {row.get(name_col, 'Unknown Name')}")
        st.caption("Member Profile")
    
    st.divider()
    
    # Iterate through all columns for the detailed list
    for col, val in row.items():
        # Skip the main image and name (already shown at top)
        if col in [name_col, img_col]:
            continue
            
        # Clean up the value
        if pd.isna(val) or str(val).strip() == "":
            display_val = "Not Provided"
        else:
            # formatting lists (semicolons) to bullets
            display_val = str(val).replace(";", "\n• ")
        
        # Render the "Bubble"
        st.markdown(f"""
        <div class="data-bubble">
            <div class="data-label">{col}</div>
            <div class="data-value">{display_val}</div>
        </div>
        """, unsafe_allow_html=True)


# --- 5. MAIN APP LOGIC ---

st.title("📂 Community Directory")
st.markdown("Upload your Google Form CSV to generate a searchable directory.")

uploaded_file = st.file_uploader("Upload CSV File", type=['csv'])

if uploaded_file:
    # Read Data
    df = pd.read_csv(uploaded_file)
    
    # Initialize Session State for AI Map (so it doesn't rerun on every click)
    if 'column_map' not in st.session_state:
        with st.spinner("🤖 AI is analyzing and renaming columns..."):
            st.session_state.column_map = get_ai_column_map(df.columns.tolist())
    
    # Apply the AI Map
    mapped_df = df.rename(columns=st.session_state.column_map)
    
    # Attempt to auto-detect Name and Image columns based on keywords
    cols_lower = [c.lower() for c in mapped_df.columns]
    
    # Heuristic: Find 'name' and 'photo'/'image'
    try:
        name_col = mapped_df.columns[[i for i, c in enumerate(cols_lower) if 'name' in c][0]]
    except:
        name_col = mapped_df.columns[1] # Fallback to 2nd column
        
    try:
        img_col = mapped_df.columns[[i for i, c in enumerate(cols_lower) if 'photo' in c or 'image' in c or 'pic' in c][0]]
    except:
        img_col = None # No image column found

    # SEARCH BAR
    search_query = st.text_input("🔍 Search for anything (Name, Skill, Idea...)", placeholder="Type 'videography' or 'student'...")
    
    # FILTERING
    if search_query:
        # Search across ALL columns (case insensitive)
        mask = mapped_df.astype(str).apply(lambda x: x.str.lower().str.contains(search_query.lower(), na=False)).any(axis=1)
        display_df = mapped_df[mask]
    else:
        display_df = mapped_df

    st.divider()
    st.markdown(f"**Showing {len(display_df)} members**")

    # GRID DISPLAY
    columns_per_row = 4
    cols = st.columns(columns_per_row)
    
    for idx, (index, row) in enumerate(display_df.iterrows()):
        col = cols[idx % columns_per_row]
        
        with col:
            # Start Card
            with st.container(border=True):
                # Image
                img_url = fix_image_link(row.get(img_col))
                if img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    # Placeholder grey box
                    st.markdown('<div style="height:150px; background:#eee; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#999;">No Photo</div>', unsafe_allow_html=True)
                
                # Name
                st.markdown(f"### {row.get(name_col, 'Unknown')}")
                
                # View Profile Button
                # Unique key is crucial for buttons in loops
                if st.button("View Profile", key=f"btn_{idx}", use_container_width=True):
                    show_profile(row, name_col, img_col)

