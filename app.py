import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# --- CONFIGURATION ---
# Paste your API key here or set it in your secrets
API_KEY = "AIzaSyDHN8h0W5ZsF8ywgLZXUiwL0cz9k-b0WkE"
genai.configure(api_key=API_KEY)

# --- HELPER FUNCTIONS ---

def get_ai_column_map(columns_list):
    """Uses AI to shorten column names."""
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"""
    I have a list of column headers from a form. 
    Create a JSON object where the keys are the original headers and the values are 
    short, human-readable, 1-3 word titles (snake_case) for that header.
    
    Rules:
    1. Map EVERY single header.
    2. Output strictly JSON. No markdown.
    3. Example: "What is your name?" -> "Full Name"
    
    Headers: {columns_list}
    """
    response = model.generate_content(prompt)
    # Clean up response to ensure it's valid JSON
    clean_text = response.text.replace('```json', '').replace('```', '')
    return json.loads(clean_text)

def fix_image_link(link):
    """Converts Google Drive share links to direct image links."""
    if pd.isna(link) or "drive.google.com" not in str(link):
        return None # Or a placeholder image URL
    
    # Logic to extract ID and format for embedding
    file_id = link.split('id=')[-1] if 'id=' in link else link.split('/d/')[-1].split('/')[0]
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"

# --- APP UI ---

st.set_page_config(layout="wide", page_title="Community Directory")

st.title("📂 Smart Intake Viewer")

# 1. FILE UPLOAD
uploaded_file = st.file_uploader("Upload your CSV", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # 2. AI PROCESSING (Only runs once)
    if 'column_map' not in st.session_state:
        with st.spinner('AI is mapping columns...'):
            st.session_state.column_map = get_ai_column_map(df.columns.tolist())
            
    # Apply the map (Rename columns for display)
    mapped_df = df.rename(columns=st.session_state.column_map)
    
    # Identify key columns using the mapped names
    # (You might need to tweak this logic or ask AI to identify the 'image' column specifically)
    # For now, let's assume the AI named them something predictable or we search for keywords
    cols = mapped_df.columns.str.lower()
    img_col = next((c for c in mapped_df.columns if 'photo' in c.lower() or 'image' in c.lower() or 'pic' in c.lower()), None)
    name_col = next((c for c in mapped_df.columns if 'name' in c.lower() and 'full' in c.lower()), mapped_df.columns[1])

    # 3. SEARCH BAR
    search_query = st.text_input("🔍 Search database...", "").lower()
    
    # Filter Logic
    if search_query:
        mask = mapped_df.astype(str).apply(lambda x: x.str.lower().str.contains(search_query, na=False)).any(axis=1)
        display_df = mapped_df[mask]
    else:
        display_df = mapped_df

    # 4. CARD GRID DISPLAY
    st.divider()
    
    # Create a grid layout
    num_columns = 4
    cols_iter = st.columns(num_columns)
    
    for index, row in display_df.iterrows():
        # Cycle through columns
        col = cols_iter[index % num_columns]
        
        with col:
            # Card Container
            with st.container(border=True):
                # Image Handling
                img_url = fix_image_link(row[img_col]) if img_col else None
                
                if img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    st.markdown("👤 **No Photo**")
                
                st.subheader(row[name_col])
                
                # 5. THE "SEMI-SCREEN" (POPUP)
                # Streamlit uses a 'expander' or 'popover' for this
                with st.popover("View Profile"):
                    st.markdown(f"## {row[name_col]}")
                    if img_url:
                        st.image(img_url, width=200)
                    
                    st.divider()
                    
                    # Iterate through ALL columns
                    for column, value in row.items():
                        if column not in [name_col, img_col]: # Skip name/img as they are at top
                            st.markdown(f"**{column}**")
                            
                            # Clean up value presentation
                            clean_val = str(value).replace(";", "\n- ") if pd.notna(value) else "Not Provided"
                            st.info(clean_val)

