"""OpenCode-inspired light, compact theme.

White canvases, layered grays, and a restrained teal / slate-blue accent set.
Google Fonts: Inter for UI, JetBrains Mono for numbers and IDs.
"""

from __future__ import annotations

import streamlit as st

FONT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=JetBrains+Mono:wght@400;500;600&display=swap"
)

CSS = f"""
<style>
@import url('{FONT_URL}');

:root {{
  --fin-bg: #ffffff;
  --fin-surface: #ffffff;
  --fin-panel: #fafafa;
  --fin-panel-2: #f4f4f5;
  --fin-border: #e4e4e7;
  --fin-border-soft: #ededf0;
  --fin-text: #27272a;
  --fin-muted: #71717a;
  --fin-faint: #a1a1aa;
  --fin-accent: #0f766e;
  --fin-accent-strong: #115e59;
  --fin-accent-soft: rgba(15, 118, 110, 0.10);
  --fin-accent-line: rgba(15, 118, 110, 0.35);
  --fin-blue: #334155;
  --fin-blue-soft: rgba(51, 65, 85, 0.08);
  --fin-good: #0f766e;
  --fin-warn: #64748b;
  --fin-bad: #1e3a5f;

  /* primary action */
  --fin-primary: #27b4f5;
  --fin-primary-border: #149bdb;
  --fin-primary-hover: #1ba7e6;
  --fin-primary-hover-border: #118fc9;

  /* supporting tokens */
  --fin-hover-border: #d4d4d8;
  --fin-sidebar-top: #fafafa;
  --fin-sidebar-bottom: #f4f4f5;
  --fin-glow-accent: rgba(15, 118, 110, 0.05);
  --fin-glow-blue: rgba(51, 65, 85, 0.04);
  --fin-candidate-border: rgba(51, 65, 85, 0.28);
  --fin-shadow: 0 1px 2px rgba(24, 24, 27, 0.04);
  --fin-radius: 12px;

  /* Streamlit-style aliases (kept in sync with the tokens above) */
  --primary-color: var(--fin-accent);
  --background-color: var(--fin-bg);
  --secondary-background-color: var(--fin-panel-2);
  --text-color: var(--fin-text);
}}

html, body, [class*="css"], .stApp {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--fin-text);
}}

.stApp {{
  background:
    radial-gradient(900px 480px at 18% -12%, var(--fin-glow-accent), transparent 60%),
    radial-gradient(700px 420px at 108% 0%, var(--fin-glow-blue), transparent 55%),
    var(--fin-bg);
}}

header[data-testid="stHeader"] {{
  background: transparent;
  height: 0;
}}
[data-testid="stToolbar"], #MainMenu, footer {{ visibility: hidden; }}

.block-container {{
  max-width: 1080px;
  padding: 2.1rem 2.2rem 5rem 2.2rem;
}}

h1, h2, h3, h4 {{
  font-family: 'Inter', sans-serif !important;
  letter-spacing: -0.025em;
  color: var(--fin-text);
}}
h1 {{ font-size: 1.55rem !important; font-weight: 650 !important; }}
h2 {{ font-size: 1.12rem !important; font-weight: 600 !important; }}
h3 {{ font-size: 0.95rem !important; font-weight: 600 !important; }}

p, label, span, div {{ color: var(--fin-text); }}
small, .stCaption, [data-testid="stCaptionContainer"] {{
  color: var(--fin-muted) !important;
}}

code, pre, .mono, [data-testid="stMetricValue"] {{
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace !important;
}}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, var(--fin-sidebar-top) 0%, var(--fin-sidebar-bottom) 100%);
  border-right: 1px solid var(--fin-border-soft);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
[data-testid="stSidebarNav"] {{ padding-top: 0.35rem; }}
[data-testid="stSidebarNav"] a {{
  border-radius: 8px;
  margin: 1px 0;
  padding: 0.38rem 0.55rem;
  color: var(--fin-muted);
  font-size: 0.86rem;
  font-weight: 500;
}}
[data-testid="stSidebarNav"] a:hover {{
  color: var(--fin-text);
  background: var(--fin-panel-2);
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  color: var(--fin-accent-strong);
  background: var(--fin-accent-soft);
  border: 1px solid var(--fin-accent-line);
}}
[data-testid="stSidebar"] hr {{
  border-color: var(--fin-border-soft);
}}

/* ---------- compact form controls ---------- */
label, [data-testid="stWidgetLabel"] p {{
  font-size: 0.71rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.075em;
  text-transform: uppercase;
  color: var(--fin-muted) !important;
}}
input, textarea, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {{
  font-family: 'Inter', sans-serif !important;
  font-size: 0.88rem !important;
  color: var(--fin-text) !important;
}}
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"],
textarea {{
  background: var(--fin-surface) !important;
  border-color: var(--fin-border) !important;
  border-radius: 9px !important;
  min-height: 2.35rem !important;
}}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within,
textarea:focus {{
  border-color: var(--fin-accent-line) !important;
  box-shadow: 0 0 0 2px var(--fin-accent-soft) !important;
}}
div[data-baseweb="select"] span, div[data-baseweb="select"] input {{
  font-size: 0.86rem !important;
  color: var(--fin-text) !important;
}}
[data-testid="stDateInput"] input {{ font-size: 0.84rem !important; }}

/* dropdown menus */
div[data-baseweb="popover"] div[role="listbox"],
div[data-baseweb="popover"] ul {{
  background: var(--fin-surface) !important;
  border-color: var(--fin-border) !important;
}}

/* number input step buttons stay quiet */
button[data-testid="stNumberInputStepUp"], button[data-testid="stNumberInputStepDown"] {{
  border-color: var(--fin-border) !important;
  background: var(--fin-panel-2) !important;
  color: var(--fin-muted) !important;
}}

/* ---------- buttons ---------- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
  font-family: 'Inter', sans-serif !important;
  font-size: 0.82rem !important;
  font-weight: 550 !important;
  border-radius: 8px !important;
  border: 1px solid var(--fin-border) !important;
  background: var(--fin-surface) !important;
  color: var(--fin-text) !important;
  min-height: 2.25rem;
  padding: 0.25rem 0.8rem;
  transition: all 120ms ease;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {{
  border-color: var(--fin-hover-border) !important;
  background: var(--fin-panel-2) !important;
  transform: translateY(-1px);
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--fin-primary) !important;
  border-color: var(--fin-primary-border) !important;
  color: var(--fin-text) !important;
}}
.stButton > button[kind="primary"] p, .stButton > button[kind="primary"] span,
.stFormSubmitButton > button[kind="primary"] p, .stFormSubmitButton > button[kind="primary"] span {{
  color: var(--fin-text) !important;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
  background: var(--fin-primary-hover) !important;
  border-color: var(--fin-primary-hover-border) !important;
  color: var(--fin-text) !important;
}}

/* ---------- pills / tabs / segmented ---------- */
[data-testid="stPills"] button, [data-testid="stSegmentedControl"] button {{
  font-size: 0.78rem !important;
  border-radius: 8px !important;
  border: 1px solid var(--fin-border) !important;
  background: var(--fin-surface) !important;
  color: var(--fin-muted) !important;
  padding: 0.2rem 0.62rem !important;
  min-height: 1.9rem;
}}
[data-testid="stPills"] button:hover, [data-testid="stSegmentedControl"] button:hover {{
  color: var(--fin-text) !important;
  border-color: var(--fin-hover-border) !important;
  background: var(--fin-panel-2) !important;
}}
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {{
  background: var(--fin-accent-soft) !important;
  border-color: var(--fin-accent-line) !important;
  color: var(--fin-accent-strong) !important;
}}
.stTabs [data-baseweb="tab-list"] {{
  gap: 4px;
  border-bottom: 1px solid var(--fin-border-soft);
}}
.stTabs [data-baseweb="tab"] {{
  height: 2rem;
  font-size: 0.8rem;
  color: var(--fin-muted);
}}
.stTabs [aria-selected="true"] {{ color: var(--fin-text); }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: var(--fin-accent) !important; }}

/* ---------- cards / containers ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--fin-surface);
  border: 1px solid var(--fin-border) !important;
  border-radius: var(--fin-radius) !important;
  padding: 0.15rem 0.3rem;
  box-shadow: var(--fin-shadow);
}}
[data-testid="stMetric"] {{
  background: var(--fin-panel);
  border: 1px solid var(--fin-border-soft);
  border-radius: 10px;
  padding: 0.7rem 0.8rem;
}}
[data-testid="stMetricLabel"] p {{
  font-size: 0.7rem !important;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--fin-muted) !important;
}}
[data-testid="stMetricValue"] {{
  font-size: 1.05rem !important;
  font-weight: 550 !important;
  color: var(--fin-text) !important;
}}

/* ---------- expander ---------- */
[data-testid="stExpander"] {{
  border: 1px solid var(--fin-border-soft);
  border-radius: 9px;
  background: var(--fin-surface);
}}
[data-testid="stExpander"] summary {{
  font-size: 0.8rem;
  color: var(--fin-muted);
}}

/* ---------- dataframe ---------- */
[data-testid="stDataFrame"] {{
  border: 1px solid var(--fin-border-soft);
  border-radius: 10px;
  overflow: hidden;
}}
[data-testid="stDataFrame"] * {{ font-family: 'Inter', sans-serif !important; font-size: 0.8rem !important; }}

/* ---------- alerts / toasts: neutral grays with a slate edge ---------- */
[data-testid="stAlert"] {{
  border-radius: 9px;
  border: 1px solid var(--fin-border) !important;
  border-left: 3px solid var(--fin-blue) !important;
  background: var(--fin-panel) !important;
  padding: 0.55rem 0.8rem;
  font-size: 0.84rem;
}}
[data-testid="stAlert"] p, [data-testid="stAlert"] span, [data-testid="stAlert"] div {{
  color: var(--fin-text) !important;
}}
[data-testid="stAlert"] svg {{
  color: var(--fin-blue) !important;
  fill: var(--fin-blue) !important;
}}
[data-testid="stNotification"], [data-testid="stToast"] {{
  font-size: 0.85rem;
  background: var(--fin-surface) !important;
  color: var(--fin-text) !important;
  border: 1px solid var(--fin-border) !important;
}}
[data-testid="stToast"] svg {{
  color: var(--fin-accent) !important;
  fill: var(--fin-accent) !important;
}}

/* ---------- custom helpers ---------- */
.fin-header {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin: 0 0 1.15rem 0;
}}
.fin-header h1 {{
  margin: 0;
  font-size: 1.55rem !important;
  line-height: 1.1;
}}
.fin-header p {{
  margin: 0.35rem 0 0 0;
  color: var(--fin-muted);
  font-size: 0.83rem;
}}
.fin-kicker {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--fin-accent);
  margin-bottom: 0.38rem;
}}
.fin-stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.55rem;
  margin: 0.2rem 0 1rem 0;
}}
.fin-stat {{
  border: 1px solid var(--fin-border-soft);
  background: var(--fin-panel);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
}}
.fin-stat .k {{
  font-size: 0.66rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--fin-faint);
}}
.fin-stat .v {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.98rem;
  font-weight: 550;
  margin-top: 0.18rem;
}}
.fin-stat .h {{ font-size: 0.7rem; color: var(--fin-muted); margin-top: 0.12rem; }}
.fin-good {{ color: var(--fin-good) !important; }}
.fin-warn {{ color: var(--fin-warn) !important; }}
.fin-bad {{ color: var(--fin-bad) !important; }}
.fin-muted {{ color: var(--fin-muted) !important; }}
.fin-accent {{ color: var(--fin-accent) !important; }}

.fin-summary {{
  border: 1px solid var(--fin-border);
  border-radius: 10px;
  overflow: hidden;
  margin: 0.35rem 0 0.75rem 0;
  background: var(--fin-surface);
}}
.fin-summary-row {{
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 0.8rem;
  padding: 0.45rem 0.7rem;
  border-bottom: 1px solid var(--fin-border-soft);
  font-size: 0.84rem;
}}
.fin-summary-row:last-child {{ border-bottom: 0; }}
.fin-summary-row .k {{ color: var(--fin-muted); }}
.fin-summary-row .v {{ font-family: 'JetBrains Mono', monospace; font-size: 0.81rem; }}

.fin-candidate {{
  border: 1px solid var(--fin-candidate-border);
  background: var(--fin-blue-soft);
  border-radius: 9px;
  padding: 0.55rem 0.7rem;
  margin-bottom: 0.4rem;
  font-size: 0.82rem;
}}
.fin-chip {{
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem;
  color: var(--fin-muted);
  background: var(--fin-panel);
  border: 1px solid var(--fin-border);
  border-radius: 999px;
  padding: 1px 7px;
  margin: 0 4px 4px 0;
}}
.fin-due {{
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
  color: var(--fin-muted);
  border: 1px solid var(--fin-border-soft);
  border-radius: 9px;
  padding: 0.45rem 0.65rem;
  margin-bottom: 0.85rem;
  background: var(--fin-panel);
}}
.fin-due b {{ color: var(--fin-text); font-weight: 550; }}

.fin-empty {{
  border: 1px dashed var(--fin-border);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  color: var(--fin-muted);
  font-size: 0.84rem;
  background: var(--fin-panel);
}}

@media (max-width: 900px) {{
  .block-container {{ padding: 1.4rem 1.1rem 4rem 1.1rem; }}
  .fin-header {{ align-items: flex-start; flex-direction: column; }}
  .fin-header h1 {{ font-size: 1.32rem !important; }}
}}
@media (max-width: 640px) {{
  .block-container {{ padding: 1.05rem 0.8rem 3.5rem 0.8rem; }}
  .fin-summary-row {{ grid-template-columns: 96px 1fr; gap: 0.5rem; }}
  .fin-stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  [data-testid="stPills"] button {{ font-size: 0.73rem !important; }}
}}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
