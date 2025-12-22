import streamlit as st
import pandas as pd
import plotly.express as px
from sqlite_utils import Database
from datetime import datetime
import json

# Setup
st.set_page_config(page_title="SlopStopper Audit", page_icon="🛡️", layout="wide")
DB_FILE = "data/slopstopper.db"

def get_db():
    return Database(DB_FILE)

# Sidebar
st.sidebar.header("🛡️ SlopStopper Control")



min_date = st.sidebar.date_input("Start Date", datetime(2025, 1, 1))
max_date = st.sidebar.date_input("End Date", datetime.now())
safety_threshold = st.sidebar.slider("Safety Threshold", 0, 100, 60, help="Videos below this score are flagged. (100=Safe, 0=Toxic)")
include_pending = st.sidebar.checkbox("Include Pending Videos", value=False)

# Data Load
@st.cache_data(ttl=60)
def load_data():
    db = get_db()
    query = "SELECT * FROM videos"
    if not include_pending:
        query += " WHERE status = 'ANALYZED'"
    
    rows = list(db.query(query))
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    
    # Parse the analysis_json field to extract deep data
    # We use json_normalize to flatten the nested structure
    def parse_json(x):
        try:
            return json.loads(x)
        except:
            return {}

    if 'analysis_json' in df.columns:
        json_data = df['analysis_json'].apply(parse_json).tolist()
        df_json = pd.json_normalize(json_data)
        # Verify we didn't lose rows or misalign
        if len(df_json) == len(df):
            df = pd.concat([df, df_json], axis=1)
            
    return df

# --- CONSTANTS & CONFIG ---
FINGERPRINT_CONFIG = {
    "Structure": {
        "col": "narrative_quality.structural_integrity",
        "opts": ["Coherent_Narrative", "Loose_Vlog_Style", "Compilation_Clips", "Incoherent_Chaos"],
        "colors": {"Coherent_Narrative": "green", "Loose_Vlog_Style": "orange", "Compilation_Clips": "orange", "Incoherent_Chaos": "red"}
    },
    "Intent": {
        "col": "narrative_quality.creative_intent",
        "opts": ["Artistic/Creative", "Informational", "Parasocial/Vlog", "Algorithmic/Slop"],
        "colors": {"Artistic/Creative": "green", "Informational": "green", "Parasocial/Vlog": "orange", "Algorithmic/Slop": "red"}
    },
    "Weirdness": {
        "col": "narrative_quality.weirdness_verdict",
        "opts": ["Normal", "Creative_Surrealism", "Lazy_Randomness", "Disturbing_Uncanny"],
        "colors": {"Normal": "green", "Creative_Surrealism": "green", "Lazy_Randomness": "red", "Disturbing_Uncanny": "red"}
    },
    "Density": {
        "col": "cognitive_nutrition.intellectual_density",
        # NOTE: DB values might be 'High (..)', we split on space
        "opts": ["High", "Medium", "Low", "Void"],
        "colors": {"High": "green", "Medium": "green", "Low": "orange", "Void": "red"}
    },
    "Volatility": {
        "col": "cognitive_nutrition.emotional_volatility",
        "opts": ["Calm", "Upbeat", "High_Stress", "Aggressive_Screaming"],
        "colors": {"Calm": "green", "Upbeat": "green", "High_Stress": "orange", "Aggressive_Screaming": "red"}
    }
}

def render_mini_fingerprint(row):
    """Generates a compact HTML row of badges for the validation metrics."""
    html = "<div style='display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px;'>"
    
    bg_map = {"green": "#d4edda", "orange": "#fff3cd", "red": "#f8d7da", "blue": "#cce5ff", "purple": "#e2e3e5"}
    text_map = {"green": "#155724", "orange": "#856404", "red": "#721c24", "blue": "#004085", "purple": "#383d41"}

    for label, cfg in FINGERPRINT_CONFIG.items():
        val = row.get(cfg['col'], 'Unknown')
        # specific handling for density split
        if label == "Density" and val and isinstance(val, str):
            val = val.split(" ")[0]
            
        color_key = cfg['colors'].get(val, 'blue')
        bg = bg_map.get(color_key, "#e2e3e5")
        fg = text_map.get(color_key, "#383d41")
        
        display_val = str(val).replace('_', ' ')
        
        badge_style = (
            f"background-color: {bg}; color: {fg}; "
            f"padding: 2px 6px; border-radius: 4px; "
            f"font-size: 0.75rem; font-weight: 600; border: 1px solid {fg};"
        )
        html += f"<div style='{badge_style}'>{label}: {display_val}</div>"
    
    html += "</div>"
    return html

df = load_data()

if df.empty:
    st.warning("No data found. RUN THE PIPELINE: `uv run src/ingest.py` -> `uv run src/analyze.py --limit 10`")
    st.stop()

# Helper: Ensure columns exist (handling cases where json might be partial)
def ensure_col(df, col, default=False):
    if col not in df.columns:
        df[col] = default
    return df

# Normalize Columns
df['safety_score'] = pd.to_numeric(df['risk_assessment.safety_score'], errors='coerce').fillna(100)
# Use the parsed JSON booleans which are more reliable/typed than SQLite 0/1 if available, else fallback
df = ensure_col(df, 'cognitive_nutrition.is_slop', False)
df = ensure_col(df, 'cognitive_nutrition.is_brainrot', False)
df = ensure_col(df, 'content_taxonomy.primary_genre', 'Unknown')
df = ensure_col(df, 'content_taxonomy.specific_topic', 'Unknown')
df = ensure_col(df, 'content_taxonomy.target_demographic', 'Unknown')

# Synthesize Quality Score (0-10) based on Narrative & Intent
# Map Structure
struct_map = {
    "Coherent_Narrative": 9.0,
    "Loose_Vlog_Style": 6.0,
    "Compilation_Clips": 4.0,
    "Incoherent_Chaos": 1.0
}
# Map Intent
intent_map = {
    "Artistic/Creative": 9.0,
    "Informational": 7.0,
    "Parasocial/Vlog": 5.0,
    "Algorithmic/Slop": 1.0
}

df['q_struct'] = df['narrative_quality.structural_integrity'].map(struct_map).fillna(5)
df['q_intent'] = df['narrative_quality.creative_intent'].map(intent_map).fillna(5)
df['Quality Score'] = (df['q_struct'] + df['q_intent']) / 2.0

# Normalize for plotting (ensure it exists)
df = ensure_col(df, 'Quality Score', 0.0)

# Rename for easier plotting
df['Is Slop'] = df['cognitive_nutrition.is_slop']
df['Is Brainrot'] = df['cognitive_nutrition.is_brainrot']
df['Genre'] = df['content_taxonomy.primary_genre']
df['Topic'] = df['content_taxonomy.specific_topic'].fillna('Generic')

# Date Filter (if timestamp available)
if 'watch_timestamp' in df.columns:
    df['watch_timestamp'] = pd.to_datetime(df['watch_timestamp'], errors='coerce')
    # Filter
    # df = df[(df['watch_timestamp'].dt.date >= min_date) & (df['watch_timestamp'].dt.date <= max_date)]

# --- GLOBAL STYLING ---
st.markdown("""
    <style>
        /* 1. HEADER: Fixed Bottom, Transparent, Overlay */
        header[data-testid="stHeader"] {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            top: auto;
            height: 3rem;
            background-color: transparent !important;
            z-index: 999;
            pointer-events: none; /* Let clicks pass through empty areas */
        }
        
        /* Make header buttons interactive */
        header[data-testid="stHeader"] > div {
            pointer-events: auto;
        }

        /* 2. CONTENT: Top aligned, no gap */
        .block-container {
            padding-top: 1rem !important;
            margin-top: 0rem !important;
        }

        /* 3. NAVIGATION: Tabs Style */
        div[role="radiogroup"] {
            display: flex;
            flex-direction: row;
            gap: 5px;
            justify-content: flex-start;
            border-bottom: 2px solid #f0f2f6;
            padding-bottom: 0px;
            margin-bottom: 10px;
            margin-top: -15px;
            /* No extra padding-left needed if we have 2.5rem top padding, 
               the buttons validly sit above the nav or to the left? 
               Actually sidebar toggle is top-left. 
               If padding-top is 2.5rem, content starts BELOW the toggle. 
               This resolves overlap comfortably. */
        }
        
        div[role="radiogroup"] label {
            background-color: transparent;
            border: 1px solid transparent; /* Prevent size jump */
            padding: 5px 12px;
            border-radius: 5px 5px 0 0;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: -2px; /* Pull down to overlap border */
        }
        
        div[role="radiogroup"] label:hover {
            background-color: #f8f9fb;
            color: #0068c9;
        }
        
        /* SELECTED STATE */
        /* Target the label checking for the checked input inside */
        div[role="radiogroup"] label:has(input:checked) {
            background-color: transparent;
            border-bottom: 3px solid #ff4b4b; /* Streamlit Red */
            color: #ff4b4b;
            font-weight: bold;
        }
        
        /* Hide default radio circle */
        div[role="radiogroup"] label > div:first-child {
            display: none !important; 
        }
        
        div[role="radiogroup"] label > div[data-testid="stMarkdownContainer"] > p {
             font-size: 1rem;
             font-weight: 600;
             margin: 0;
             line-height: 1.2;
        }
        
        /* Remove default radio spacing */
        div.row-widget.stRadio > div {
            flex-direction: row;
            gap: 0px;
        }
        
        /* SHINK HEADERS */
        h5 {
            padding-top: 0px !important; 
            margin-top: 5px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION ---
# Use radio button for stable persistence instead of st.tabs which was resetting
nav_options = ["🧠 The Diet", "🚨 The Audit", "🔍 Deep Dive"]

# Ensure persistence
if 'nav_selection' not in st.session_state:
    st.session_state.nav_selection = nav_options[0]



selected_tab = st.radio(
    "Navigation", 
    nav_options, 
    horizontal=True, 
    label_visibility="collapsed",
    key="nav_selection"
)

# Removed st.divider() for density

if selected_tab == nav_options[0]:
    # Use full width for the taxonomy immediately
    
    # Dimension 2: Taxonomy (Genre/Topic)
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.subheader("📚 Taxonomy")
        if not df.empty:
            # Use full DF for leaf-level detail
            tmap_df = df.copy()
            tmap_df['Value'] = 1
            # Ensure string types for path components
            tmap_df['Genre'] = tmap_df['Genre'].astype(str)
            tmap_df['Topic'] = tmap_df['Topic'].astype(str)
            tmap_df['video_id'] = tmap_df['video_id'].astype(str)
            
            # Create a combined label for the leaf node
            tmap_df['LeafLabel'] = tmap_df['title'] + " (" + tmap_df['video_id'] + ")"

            fig_tree = px.treemap(
                tmap_df, 
                path=[px.Constant("YouTube History"), 'Genre', 'Topic', 'LeafLabel'], 
                values='Value',
                color='safety_score',
                color_continuous_scale='RdYlGn',
                range_color=[0, 100],
                title="Genre & Topic Distribution",
                # Disable hover tooltips as requested
                hover_data={
                    'title': False,
                    'channel_name': False,
                    'video_id': False,
                    'LeafLabel': False,
                    'Genre': False,
                    'Topic': False,
                    'Value': False,
                    'safety_score': False
                }
            )
            # Update traces to forcefully disable hover info if hover_data isn't enough
            fig_tree.update_traces(hoverinfo='none', hovertemplate=None)
            
            st.plotly_chart(fig_tree, use_container_width=True)
            
    with r1c2:
        st.subheader("⚠️ Risk Radar (Aggregate)")
        flag_cols = [c for c in df.columns if 'risk_assessment.flags.' in c]
        if flag_cols:
            risk_counts = df[flag_cols].sum().reset_index()
            risk_counts.columns = ['Flag', 'Count']
            # IMPROVEMENT: Format Flag names nicely (remove prefix, replace underscores, title case)
            risk_counts['Flag'] = risk_counts['Flag'].str.replace('risk_assessment.flags.', '') \
                                                     .str.replace('_', ' ') \
                                                     .str.title()
            
            fig_radar = px.line_polar(
                risk_counts, 
                r='Count', 
                theta='Flag', 
                line_close=True,
                title="Risk Profile",
                template="plotly_dark"
            )
            fig_radar.update_traces(fill='toself')
            st.plotly_chart(fig_radar, use_container_width=True)

    st.divider()

    
    # --- TIME SERIES ANALYSIS ---
    st.subheader("📈 Evolutionary Trends (Time Series)")
    st.caption("How your content consumption is changing over time.")

    if 'watch_timestamp' in df.columns:
        # Prepare Time Series Data
        ts_df = df.copy()
        ts_df['Date'] = ts_df['watch_timestamp'].dt.date
        
        # Helper for Stacked Bar
        def plot_time_series(dataframe, col_name, title, color_map_dict=None, custom_order=None):
            if col_name not in dataframe.columns:
                return None
            
            # Aggregate: Count by Date + Category
            agg = dataframe.groupby(['Date', col_name]).size().reset_index(name='Count')
            
            # CLEANUP: Prettify Labels
            # 1. Clean values (replace '_' with ' ')
            clean_col = "Category" # Generic name for the legend title, or we can use 'title'
            agg[clean_col] = agg[col_name].astype(str).str.replace('_', ' ')
            
            # 2. Update Color Map to match cleaned labels
            clean_color_map = {}
            if color_map_dict:
                for k, v in color_map_dict.items():
                    clean_k = str(k).replace('_', ' ')
                    clean_color_map[clean_k] = v
           
            # 3. Handle Custom Order (also clean the order labels)
            plot_orders = {}
            if custom_order:
                # Clean the custom order strings too to match the data
                clean_order = [str(x).replace('_', ' ') for x in custom_order]
                plot_orders = {clean_col: clean_order}
                    
            # Create Plot
            fig = px.bar(
                agg, 
                x='Date', 
                y='Count', 
                color=clean_col, # Use cleaned column
                title=title,
                color_discrete_map=clean_color_map, # Use list of mapped colors
                template="plotly_dark",
                labels={clean_col: title}, # Rename Legend Title to match Chart Title
                category_orders=plot_orders 
            )
            # Remove gap between bars to look like a stream/density
            fig.update_layout(bargap=0.1) 
            return fig

        # Define Color Maps (Matching Deep Dive)
        # 1. Structure
        struct_colors = {
            "Coherent_Narrative": "green", 
            "Loose_Vlog_Style": "orange", 
            "Compilation_Clips": "orange", 
            "Incoherent_Chaos": "red"
        }
        # 2. Intent
        intent_colors = {
            "Artistic/Creative": "green", 
            "Informational": "green", 
            "Parasocial/Vlog": "orange", 
            "Algorithmic/Slop": "red"
        }
        # 3. Weirdness
        weird_colors = {
            "Normal": "green", 
            "Creative_Surrealism": "green", 
            "Lazy_Randomness": "orange", 
            "Disturbing_Uncanny": "red"
        }
        # 4. Density (Prefix matching logic needed? The DB values are consistent strings usually)
        # The DB strings might be "High (..)" so we need to maybe clean them first or mapped exact strings.
        # Let's clean the DF column for plotting first like we did for Deep Dive display?
        # For now, assuming exact matches or we use the raw strings.
        # Deep Dive logic: `short_val = db_val.split(" ")[0]`. Let's apply that.
        ts_df['density_clean'] = ts_df['cognitive_nutrition.intellectual_density'].apply(lambda x: str(x).split(' ')[0] if pd.notnull(x) else "Unknown")
        dens_colors = {"High": "green", "Medium": "green", "Low": "orange", "Void": "red"}
        
        # 5. Volatility
        vol_colors = {
            "Calm": "green", 
            "Upbeat": "green", 
            "High_Stress": "orange", 
            "Aggressive_Screaming": "red"
        }

        # 6. Video Format (from metadata)
        # Check column existence safely
        col_fmt = 'video_metadata.format'
        if col_fmt not in ts_df.columns:
            ts_df[col_fmt] = "Unknown"
        else:
            ts_df[col_fmt] = ts_df[col_fmt].fillna("Unknown")
            
        fmt_colors = {
            "Standard_Landscape": "blue",
            "vertical_short": "orange", # Guessing potential value, or let plotly decide
            "square": "purple"
        }

        # 7. Perceived Duration (from metadata)
        col_dur = 'video_metadata.duration_perceived'
        if col_dur not in ts_df.columns:
             ts_df[col_dur] = "Unknown"
        else:
             ts_df[col_dur] = ts_df[col_dur].fillna("Unknown")

        # Map typical values if we want specific colors (e.g. Short=Orange, Long=Blue)
        # Values like "Medium (5-20 min)", "Short (< 5 min)" etc.
        # We can leave colors dynamic or try to map. 
        # Let's map "Short..." to orange-ish if possible, but dynamic is safer for unknown strings.
        dur_perceived_colors = {
            "Micro (<1 min)": "orange",
            "Short (1-5 min)": "orange",
            "Medium (5-20 min)": "blue",
            "Long (20+ min)": "blue",
            "Extra Long (> 60 min)": "purple"
        }
        
        # Define logical order
        dur_order = [
            "Micro (<1 min)",
            "Short (1-5 min)",
            "Medium (5-20 min)",
            "Long (20+ min)",
            "Extra Long (> 60 min)"
        ]

        # Plot Rows
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            st.plotly_chart(plot_time_series(ts_df, 'narrative_quality.structural_integrity', "Structure", struct_colors), use_container_width=True)
            st.plotly_chart(plot_time_series(ts_df, 'narrative_quality.weirdness_verdict', "Weirdness", weird_colors), use_container_width=True)
            st.plotly_chart(plot_time_series(ts_df, 'cognitive_nutrition.emotional_volatility', "Emotional Volatility", vol_colors), use_container_width=True)
            
        with r3c2:
            st.plotly_chart(plot_time_series(ts_df, 'narrative_quality.creative_intent', "Intent", intent_colors), use_container_width=True)
            st.plotly_chart(plot_time_series(ts_df, 'density_clean', "Intellectual Density", dens_colors), use_container_width=True)
            
        # New Row: Format & Perceived Duration
        r4c1, r4c2 = st.columns(2)
        with r4c1:
             st.plotly_chart(plot_time_series(ts_df, col_fmt, "Video Format", fmt_colors), use_container_width=True)
        with r4c2:
             st.plotly_chart(plot_time_series(ts_df, col_dur, "Perceived Duration", dur_perceived_colors, custom_order=dur_order), use_container_width=True)

    else:
        st.warning("No timestamp data available for Time Series.")



    st.divider()

    # Dimension 3: Quality vs Safety (Quadrants)
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.subheader("🎨 Quality vs Safety (The Quadrants)")
        st.caption("Top Left: Unsafe but Art. Top Right: Safe & Good.")
        
        sc_x = 'safety_score'
        sc_y = 'Quality Score'
        
        if not df.empty and sc_x in df.columns and sc_y in df.columns:
            fig_scatter = px.scatter(
                df, 
                x=sc_x, 
                y=sc_y, 
                color='Genre', 
                hover_data=['title', 'Topic'],
                title="Quality (Narrative) vs Safety",
                text='title' if len(df) < 50 else None # Only show labels if few points
            )
            
            fig_scatter.add_hline(y=5, line_dash="dot", annotation_text="Coherence Threshold")
            fig_scatter.add_vline(x=safety_threshold, line_dash="dot", annotation_text="Safety Threshold")
            
            fig_scatter.add_annotation(x=90, y=9, text="Safe & Good", showarrow=False, font=dict(color="green"))
            fig_scatter.add_annotation(x=30, y=9, text="Unsafe but Art", showarrow=False, font=dict(color="orange"))
            fig_scatter.add_annotation(x=90, y=2, text="Safe Slop", showarrow=False, font=dict(color="blue"))
            fig_scatter.add_annotation(x=30, y=2, text="Danger Zone", showarrow=False, font=dict(color="red"))
            
            st.plotly_chart(fig_scatter, use_container_width=True)

    with r2c2:
        st.empty()

elif selected_tab == nav_options[1]:
    st.markdown("### 🛑 The Audit (Action Items)")
    
    risky_videos = df[df['safety_score'] < safety_threshold]
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("💀 The Kill List")
        if not risky_videos.empty:
            kill_list = risky_videos.groupby(['channel_name']).agg({
                'video_id': 'count', 
                'safety_score': 'mean'
            }).reset_index()
            kill_list.columns = ['Channel', 'Violations', 'Avg Safety']
            kill_list = kill_list.sort_values('Avg Safety', ascending=True)
            
            # Interactive Table
            selection = st.dataframe(
                kill_list.style.background_gradient(cmap='RdYlGn', subset=['Avg Safety']), 
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            # Handle Selection
            if selection.selection.rows:
                selected_row_idx = selection.selection.rows[0]
                selected_channel = kill_list.iloc[selected_row_idx]['Channel']
                
                st.markdown(f"#### 🔍 Inspecting: **{selected_channel}**")
                channel_bad_vids = risky_videos[risky_videos['channel_name'] == selected_channel]
                
                for _, vid in channel_bad_vids.head(5).iterrows():
                     with st.expander(f"🚫 {vid['title'][:50]}...", expanded=True):
                         st.error(f"**Safety Score:** {vid['safety_score']} | **Reason:** {vid.get('verdict.reason', 'N/A')}")
                         st.markdown(render_mini_fingerprint(vid), unsafe_allow_html=True)
                         st.video(vid['video_url'])
            else:
                st.info("👆 Select a channel to see their violations.")
                
        else:
            st.success("No active threats found.")
            
    with col2:
        st.subheader("🔦 Risk Spotlight")
        
        spot_tabs = st.tabs(["💀 Brainrot", "🤬 Aggression", "🧟 Slop"])
        
        def show_toxic_video(videorow):
             with st.expander(f"⚠️ {videorow['title'][:40]}...", expanded=False):
                st.write(f"**Reason:** {videorow.get('verdict.reason', 'N/A')}")
                st.markdown(render_mini_fingerprint(videorow), unsafe_allow_html=True)
                st.video(videorow['video_url'])
        
        with spot_tabs[0]:
            # Brainrot: High Weirdness OR Explicit Brainrot Flag
            br_mask = (df['cognitive_nutrition.is_brainrot'] == True) | (df['narrative_quality.weirdness_verdict'] == 'Disturbing_Uncanny')
            br_vids = df[br_mask]
            if not br_vids.empty:
                for _, vid in br_vids.head(3).iterrows():
                    show_toxic_video(vid)
            else:
                st.caption("No brainrot detected.")

        with spot_tabs[1]:
            # Aggression: High Volatility
            agg_mask = (df['cognitive_nutrition.emotional_volatility'] == 'Aggressive_Screaming')
            agg_vids = df[agg_mask]
            if not agg_vids.empty:
                for _, vid in agg_vids.head(3).iterrows():
                    show_toxic_video(vid)
            else:
                st.caption("No aggression detected.")
                
        with spot_tabs[2]:
            # Slop: Explicit Slop Flag
            slop_mask = (df['cognitive_nutrition.is_slop'] == True)
            slop_vids = df[slop_mask]
            if not slop_vids.empty:
                for _, vid in slop_vids.head(3).iterrows():
                    show_toxic_video(vid)
            else:
                st.caption("No slop detected.")
    


elif selected_tab == nav_options[2]:
    # Custom CSS for compact layout and bigger tabs
    st.markdown("""
        <style>
            /* Move header to bottom */
            header[data-testid="stHeader"] {
                position: fixed;
                bottom: 0;
                left: 0;
                top: auto;
                background-color: transparent !important;
                z-index: 999;
            }
            /* Reset main content spacing */
            .block-container {
                padding-top: 1rem !important; 
                margin-top: 0rem !important;
            }
            .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
                font-size: 1.2rem;
                font-weight: bold;
            }
            h5 {
                padding-top: 0px !important; 
                margin-top: 0px !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # 1. Select (Left) & Search (Right)
    c_select, c_search = st.columns([2, 1], gap="small")
    
    with c_search:
        search_term = st.text_input("Search", "", label_visibility="collapsed", placeholder="Search Title, ID, Channel", key="deep_dive_search")
    
    filtered_df = df.copy()
    if search_term:
        mask = (
            df['title'].str.contains(search_term, case=False, na=False) | 
            df['video_id'].str.contains(search_term, case=False, na=False) |
            df['channel_name'].str.contains(search_term, case=False, na=False)
        )
        filtered_df = df[mask]
        
    if not filtered_df.empty:
        vid_options = (filtered_df['video_id'] + " | " + filtered_df['channel_name'].fillna('Unknown') + " | " + filtered_df['title']).tolist()
        
        if 'deep_dive_video_idx' not in st.session_state:
            st.session_state.deep_dive_video_idx = 0
            
        with c_select:
            selected_idx = st.selectbox(
                "Select Video", 
                range(len(vid_options)), 
                format_func=lambda i: vid_options[i],
                label_visibility="collapsed",
                key="deep_dive_video_idx"
            )
        
        selected_vid_id = vid_options[selected_idx].split(" | ")[0]
        row = df[df['video_id'] == selected_vid_id].iloc[0]

        
        # ==================== LAYOUT: Video (Left), Fingerprint (Right) ====================
        
        # ==================== LAYOUT: Video (Left), Fingerprint (Right) ====================
        left_col, right_col = st.columns([1, 1.5], gap="small")
        
        with left_col:
            # 1. Channel | Title
            channel_id = row.get('channel_id', '')
            channel_link = f"[{row['channel_name']}](https://www.youtube.com/channel/{channel_id})" if channel_id else row['channel_name']
            st.markdown(f"##### {channel_link} | {row['title']}")
            
            # 2. Summary
            st.info(row.get('summary', 'No summary available.'))

            # 3. Verdict (Colored Box)
            verdict_action = row.get('verdict.action', 'Unknown')
            verdict_reason = row.get('verdict.reason', '')
            verdict_map = {
                "Approve": ("🟢 Approve", st.success), 
                "Monitor": ("🟡 Monitor", st.warning), 
                "Block_Video": ("🔴 Block Video", st.error), 
                "Block_Channel": ("⛔ Block Channel", st.error)
            }
            label, func = verdict_map.get(verdict_action, ("⚪ Unknown", st.info))
            func(f"**Verdict: {label}**\n\n{verdict_reason}")

            # 4. Video
            st.video(row['video_url'])

        with right_col:
            st.markdown("##### 🧬 Content Fingerprint")
            
            # Helper to generate HTML for a single scale row
            def get_scale_html(label, current_val, options, color_map=None):
                html = f"<div style='margin-bottom: 10px;'><div style='font-weight:bold; margin-bottom:4px;'>{label}</div><div style='display: flex; gap: 5px;'>"
                for opt in options:
                    is_selected = (opt == current_val)
                    bg_color = "#f0f2f6"
                    text_color = "#31333f"
                    border = "1px solid #e0e0e0"
                    
                    if is_selected:
                        base_color = "blue"
                        if color_map: base_color = color_map.get(opt, "blue")
                        bg_map = {"green": "#d4edda", "orange": "#fff3cd", "red": "#f8d7da", "blue": "#cce5ff"}
                        text_map = {"green": "#155724", "orange": "#856404", "red": "#721c24", "blue": "#004085"}
                        bg_color = bg_map.get(base_color, "#cce5ff")
                        text_color = text_map.get(base_color, "#004085")
                        border = f"2px solid {text_color}"
                    
                    div_style = (
                        f"flex: 1; "
                        f"background-color: {bg_color}; "
                        f"color: {text_color}; "
                        f"border: {border}; "
                        f"border-radius: 4px; "
                        f"padding: 4px; "
                        f"text-align: center; "
                        f"font-size: 11px; "
                        f"font-weight: {'bold' if is_selected else 'normal'};"
                    )
                    
                    label_text = opt.replace('_', ' ').replace(' ', '&nbsp;')
                    html += f'<div style="{div_style}">{label_text}</div>'
                html += "</div></div>"
                return html

            # Build all HTML first
            full_html = ""
            
            # 1. Structure
            struct_opts = ["Coherent_Narrative", "Loose_Vlog_Style", "Compilation_Clips", "Incoherent_Chaos"]
            struct_colors = {"Coherent_Narrative": "green", "Loose_Vlog_Style": "orange", "Compilation_Clips": "orange", "Incoherent_Chaos": "red"}
            full_html += get_scale_html("Structure", row.get('narrative_quality.structural_integrity', 'Unknown'), struct_opts, struct_colors)
            
            # 2. Intent
            intent_opts = ["Artistic/Creative", "Informational", "Parasocial/Vlog", "Algorithmic/Slop"]
            intent_colors = {"Artistic/Creative": "green", "Informational": "green", "Parasocial/Vlog": "orange", "Algorithmic/Slop": "red"}
            full_html += get_scale_html("Intent", row.get('narrative_quality.creative_intent', 'Unknown'), intent_opts, intent_colors)
            
            # 3. Weirdness
            weird_opts = ["Normal", "Creative_Surrealism", "Lazy_Randomness", "Disturbing_Uncanny"]
            weird_colors = {"Normal": "green", "Creative_Surrealism": "green", "Lazy_Randomness": "red", "Disturbing_Uncanny": "red"}
            full_html += get_scale_html("Weirdness", row.get('narrative_quality.weirdness_verdict', 'Unknown'), weird_opts, weird_colors)
            
            # 4. Density
            dens_opts = ["High", "Medium", "Low", "Void"]
            # Map long values from DB to short display values
            db_val = row.get('cognitive_nutrition.intellectual_density', 'Unknown')
            short_val = db_val.split(" ")[0] if db_val else "Unknown" # Extract "High" from "High (Educational)"
            dens_colors = {"High": "green", "Medium": "green", "Low": "orange", "Void": "red"}
            full_html += get_scale_html("Intellectual Density", short_val, dens_opts, dens_colors)
            
            # 5. Emotional Volatility
            vol_opts = ["Calm", "Upbeat", "High_Stress", "Aggressive_Screaming"]
            vol_colors = {"Calm": "green", "Upbeat": "green", "High_Stress": "orange", "Aggressive_Screaming": "red"}
            full_html += get_scale_html("Emotional Volatility", row.get('cognitive_nutrition.emotional_volatility', 'Unknown'), vol_opts, vol_colors)
            
            st.markdown(full_html, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Visual & Flags
            entities = row.get('visual_grounding.detected_entities', [])
            setting = row.get('visual_grounding.setting', 'Unknown')
            st.markdown(f"**👁️ Visual Setting:** {setting} — {', '.join(entities) if isinstance(entities, list) else entities}")
            
            flag_cols = [c for c in df.columns if 'risk_assessment.flags.' in c]
            active_flags = [c.replace('risk_assessment.flags.', '').replace('_', ' ').title() for c in flag_cols if row.get(c, False)]
            if active_flags:
                st.error(f"⚠️ **Risk Flags:** {', '.join(active_flags)}")
            else:
                st.success("✅ No Risk Flags Detected")

        # ==================== RAW JSON (Bottom) ====================
        st.markdown("---")
        st.subheader("📄 Raw Analysis JSON")
        try:
            analysis_json = json.loads(row['analysis_json']) if isinstance(row['analysis_json'], str) else {}
            st.json(analysis_json)
        except:
             st.error("Invalid JSON data")
    else:
        st.info("No videos found matching search.")

