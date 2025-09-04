import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo
import io
import os

# -----------------------------
# Constants
# -----------------------------
ELEMENT_TYPES = ['role', 'goal', 'audience', 'context', 'output', 'tone']
CSV_COLUMNS = ['title', 'type', 'content']
PROMPT_HISTORY_COLUMNS = ['name', 'timestamp', 'prompt']
TZ = ZoneInfo("America/Denver")

# -----------------------------
# Custom theme and styling
# -----------------------------
def set_theme():
    st.markdown("""
    <style>
    :root {
        --background: #000000;
        --foreground: #FAFAFA;
        --muted: #27272A;
        --muted-foreground: #A1A1AA;
        --popover: #18181B;
        --border: #27272A;
        --input: #27272A;
        --primary: #FAFAFA;
        --secondary: #27272A;
    }

    .stApp { background-color: var(--background); color: var(--foreground); }

    /* Headings */
    h1, h2, h3, h4, h5, h6 { color: var(--foreground) !important; }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
        background-color: var(--input) !important;
        color: var(--foreground) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: var(--secondary) !important;
        color: var(--foreground) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stButton > button:hover { background-color: var(--muted) !important; border-color: var(--primary) !important; }

    /* Expanders */
    details[data-testid="stExpander"] {
        background-color: var(--secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        padding: 2px 6px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 1px; background-color: var(--background); }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--secondary);
        border-radius: 6px 6px 0 0;
        padding: 8px 16px;
        color: var(--muted-foreground);
        border: 1px solid var(--border);
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--muted);
        color: var(--foreground);
        border-bottom-color: var(--muted);
    }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------
# Utilities
# -----------------------------
def _ensure_csv(path: str, columns: List[str]) -> pd.DataFrame:
    """Create the CSV if missing. If present but missing cols, add them."""
    if not os.path.exists(path):
        df = pd.DataFrame(columns=columns)
        df.to_csv(path, index=False)
        return df
    df = pd.read_csv(path)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        for c in missing:
            df[c] = ""  # add empty columns
        df = df[columns]  # reorder
        df.to_csv(path, index=False)
    return df

def _safe_concat(df: pd.DataFrame, new_row: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df, new_row], ignore_index=True)

def _iso_now() -> str:
    return datetime.now(tz=TZ).isoformat()

# -----------------------------
# Data management
# -----------------------------
class DataManager:
    @staticmethod
    def load_data(filename: str, columns: List[str]) -> pd.DataFrame:
        return _ensure_csv(filename, columns)

    @staticmethod
    def save_data(df: pd.DataFrame, filename: str) -> None:
        df.to_csv(filename, index=False)

    @staticmethod
    def save_prompt(name: str, prompt: str) -> None:
        df = DataManager.load_data('prompt_history.csv', PROMPT_HISTORY_COLUMNS)
        new_row = pd.DataFrame({
            'name': [name],
            'timestamp': [_iso_now()],
            'prompt': [prompt]
        })
        df = _safe_concat(df, new_row)
        DataManager.save_data(df, 'prompt_history.csv')

# -----------------------------
# UI Components
# -----------------------------
class SidebarTools:
    @staticmethod
    def render(df_elements: pd.DataFrame):
        st.sidebar.subheader("Manage Elements CSV")
        # Download
        buf = io.StringIO()
        df_elements.to_csv(buf, index=False)
        st.sidebar.download_button("Download elements.csv", buf.getvalue(), file_name="prompt_elements.csv", mime="text/csv")

        # Upload/replace
        uploaded = st.sidebar.file_uploader("Upload elements CSV", type=["csv"])
        if uploaded is not None:
            try:
                new_df = pd.read_csv(uploaded)
                # Validate required columns
                if not all(c in new_df.columns for c in CSV_COLUMNS):
                    st.sidebar.error(f"CSV must have columns: {CSV_COLUMNS}")
                else:
                    DataManager.save_data(new_df[CSV_COLUMNS], 'prompt_elements.csv')
                    st.sidebar.success("Elements uploaded and saved.")
                    st.rerun()
            except Exception as e:
                st.sidebar.error(f"Upload failed: {e}")

class ElementCreator:
    @staticmethod
    def render():
        with st.expander("Create New Element", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                element_type = st.selectbox("Type", ELEMENT_TYPES, key="new_type")
                title = st.text_input("Title", key="new_title", placeholder="Short, unique name")
            with col2:
                content = st.text_area("Content", key="new_content", height=120, placeholder="What this element says/does")

            if st.button("Add Element", key="add_element"):
                if not title.strip():
                    st.error("Title is required.")
                    return
                if not content.strip():
                    st.error("Content is required.")
                    return
                df = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)
                if ((df['title'] == title) & (df['type'] == element_type)).any():
                    st.warning("An element with this title and type already exists.")
                    return
                new_row = pd.DataFrame({'title': [title.strip()], 'type': [element_type], 'content': [content.strip()]})
                df = _safe_concat(df, new_row)
                DataManager.save_data(df, 'prompt_elements.csv')
                st.success("Element added successfully!")

class ElementEditor:
    @staticmethod
    def render():
        df = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)

        if df.empty:
            st.warning("No elements found. Please create some elements first.")
            return

        # Search + filter
        colf1, colf2 = st.columns([2,1])
        with colf1:
            q = st.text_input("Search (title/content)", value="")
        with colf2:
            all_types = ['All'] + sorted(df['type'].dropna().unique().tolist())
            selected_type = st.selectbox("Filter by Type", all_types, key="filter_type")

        mask = pd.Series([True]*len(df))
        if selected_type != 'All':
            mask &= (df['type'] == selected_type)
        if q.strip():
            ql = q.lower()
            mask &= (df['title'].str.lower().str.contains(ql) | df['content'].str.lower().str.contains(ql))

        filtered_df = df[mask].copy()

        if filtered_df.empty:
            st.warning("No elements match your filters.")
            return

        # Sort for consistency
        filtered_df = filtered_df.sort_values(by=['type', 'title']).reset_index()

        for _, row in filtered_df.iterrows():
            ElementEditor._render_element(row['index'], row, df)

    @staticmethod
    def _render_element(orig_index: int, row: Dict[str, Any], df: pd.DataFrame):
        with st.expander(f"{row['title']} ({row['type']})", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                new_title = st.text_input("Title", value=row['title'], key=f"title_{orig_index}")
                new_type = st.selectbox("Type", ELEMENT_TYPES,
                                        index=ELEMENT_TYPES.index(row['type']) if row['type'] in ELEMENT_TYPES else 0,
                                        key=f"type_{orig_index}")
            with col2:
                new_content = st.text_area("Content", value=row['content'], key=f"content_{orig_index}", height=120)

            colb1, colb2, colb3 = st.columns([1,1,2])
            with colb1:
                if st.button("Update", key=f"update_{orig_index}"):
                    if not new_title.strip():
                        st.error("Title cannot be empty.")
                        return
                    if not new_content.strip():
                        st.error("Content cannot be empty.")
                        return
                    df.at[orig_index, 'title'] = new_title.strip()
                    df.at[orig_index, 'type'] = new_type
                    df.at[orig_index, 'content'] = new_content.strip()
                    DataManager.save_data(df, 'prompt_elements.csv')
                    st.success("Updated successfully!")
                    st.rerun()
            with colb2:
                if st.button("Delete", key=f"delete_{orig_index}"):
                    df = df.drop(index=orig_index).reset_index(drop=True)
                    DataManager.save_data(df, 'prompt_elements.csv')
                    st.success("Deleted successfully!")
                    st.rerun()

class PromptBuilder:
    @staticmethod
    def render():
        df = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)

        col1, col2, col3 = st.columns(3)
        selections = {}
        with col1:
            selections['role'] = PromptBuilder._create_section("Role", 'role', df)
            selections['goal'] = PromptBuilder._create_section("Goal", 'goal', df)
        with col2:
            selections['audience'] = PromptBuilder._create_section("Target Audience", 'audience', df, multi_select=True)
            selections['context'] = PromptBuilder._create_section("Context", 'context', df, multi_select=True)
        with col3:
            selections['output'] = PromptBuilder._create_section("Output", 'output', df, multi_select=True)
            selections['tone'] = PromptBuilder._create_section("Tone", 'tone', df)

        recursive_feedback = st.checkbox("Request recursive feedback", value=False,
                                         help="Adds a line asking the model to ask clarifying questions first.")

        prompt = PromptBuilder._generate_prompt(selections, df, recursive_feedback)
        PromptBuilder._display_prompt(prompt)

    @staticmethod
    def _create_section(title: str, element_type: str, df: pd.DataFrame, multi_select: bool = False) -> Dict[str, Any]:
        elements = df[df['type'] == element_type].copy()
        titles = elements['title'].tolist()
        options = ["Skip", "Write your own"] + titles

        if multi_select:
            selected = st.multiselect(title, options, default=["Skip"], key=f"select_{element_type}")
        else:
            selected = st.selectbox(title, options, key=f"select_{element_type}")

        # For custom text, use a textarea if multi-select (can be long)
        custom_widget = st.text_area if multi_select else st.text_input
        custom_content = ""
        wants_custom = (("Write your own" in selected) if multi_select else (selected == "Write your own"))
        if wants_custom:
            custom_content = custom_widget(f"Custom {title}", key=f"custom_{element_type}", height=100 if multi_select else None)

        return {
            'selected': selected,
            'custom': (custom_content or "").strip(),
            'elements': elements
        }

    @staticmethod
    def _generate_prompt(selections: Dict[str, Dict], df: pd.DataFrame, recursive_feedback: bool) -> str:
        prompt_parts = []

        def get_content_by_title(title: str) -> Optional[str]:
            # In case of duplicate titles, just take the first
            match = df[df['title'] == title]
            if match.empty:
                return None
            return str(match['content'].values[0])

        for section, data in selections.items():
            sel = data['selected']
            # Skip logic
            if (isinstance(sel, list) and (not sel or set(sel) == {"Skip"})) or (isinstance(sel, str) and sel == "Skip"):
                continue

            section_title = section.title()
            if section == 'audience':
                section_title = "Target Audience"

            # Multi-select sections
            if section in ['audience', 'context', 'output']:
                parts = []
                if isinstance(sel, list):
                    for item in sel:
                        if item in ("Skip", "Write your own"):
                            continue
                        c = get_content_by_title(item)
                        if c: parts.append(c)
                # Custom content (even if also chose prebuilt)
                if data['custom']:
                    parts.append(data['custom'])
                content = "\n".join(p for p in parts if p)
                if content:
                    prompt_parts.append(f"{section_title}:\n{content}")

            # Single-select sections
            else:
                if isinstance(sel, str) and sel == "Write your own":
                    content = data['custom']
                else:
                    content = get_content_by_title(sel if isinstance(sel, str) else "")
                if content:
                    prompt_parts.append(f"{section_title}: {content}")

        prompt = "\n\n".join(prompt_parts)

        if recursive_feedback:
            prompt += (
                "\n\nBefore you provide the response, ask any clarifying questions that "
                "would improve the output. If you already have enough info, proceed."
            )

        return prompt

    @staticmethod
    def _display_prompt(prompt: str):
        st.text_area("Generated Prompt", value=prompt, height=280, key="generated_prompt")
        st.info("Tip: Click into the box to edit; use Ctrl/Cmd+A then copy to grab the whole thing.")

        col1, col2 = st.columns(2)
        with col1:
            prompt_name = st.text_input("Prompt Name", placeholder="e.g., Cold outreach v2")
        with col2:
            if st.button("Save Prompt"):
                if prompt_name and prompt.strip():
                    DataManager.save_prompt(prompt_name.strip(), prompt.strip())
                    st.success("Prompt saved successfully!")
                else:
                    st.error("Please provide both a name and non-empty prompt.")

class PromptBrowser:
    @staticmethod
    def render():
        df = DataManager.load_data('prompt_history.csv', PROMPT_HISTORY_COLUMNS)
        if df.empty:
            st.warning("No prompts found. Create and save some prompts first.")
            return

        # Sort newest first (ISO timestamps sort lexicographically fine)
        df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)

        # Simple search
        q = st.text_input("Search saved prompts")
        if q.strip():
            ql = q.lower()
            df = df[df['prompt'].str.lower().str.contains(ql) | df['name'].str.lower().str.contains(ql)]

        for index, row in df.iterrows():
            with st.expander(f"{row['name']} — {row['timestamp']}", expanded=False):
                st.text_area("Prompt Content", value=row['prompt'], height=160, key=f"prompt_{index}")
                # quick copy button export
                st.code(row['prompt'])

# -----------------------------
# App
# -----------------------------
def main():
    st.set_page_config(layout="wide", page_title="Aaron's Prompt Creation Tool")
    set_theme()
    st.title("Aaron's Prompt Creation Tool")

    # Ensure base CSV exists early so Sidebar can download
    df_elements = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)
    SidebarTools.render(df_elements)

    tabs = st.tabs(["Element Creator", "Element Editor", "Prompt Builder", "Browse Prompts"])
    with tabs[0]:
        ElementCreator.render()
    with tabs[1]:
        ElementEditor.render()
    with tabs[2]:
        PromptBuilder.render()
    with tabs[3]:
        PromptBrowser.render()

if __name__ == "__main__":
    main()
