# 📊 Cloud-Native Multi-User Personal Finance Tracker

A lightweight, mobile-responsive, Python-powered personal finance tracker that leverages a master Google Sheet as a cloud database. Designed for households or individuals who want real-time financial analytics, dynamic category management, and privacy controls—all without the friction of app login screens or paid infrastructure.

---

## ✨ Key Features

* **📱 Cross-Platform Accessibility:** Hosted via Streamlit Community Cloud. Open it instantly on any desktop, tablet, or smartphone browser with zero downloads required.
* **☁️ Cloud-Native Datastore:** Powered by Google Sheets API (`gspread`). All transactions, investments, and custom categories live securely in your personal Google Drive.
* **👥 Multi-User & Privacy Controls:** Features a lightweight profile switcher in the sidebar. Users can log their own expenses, flag items as "Private" to hide them from combined views, and allow administrators to toggle between individual and combined household analytics.
* **📊 Real-Time Analytics Dashboard:** Interactive Plotly charts showing monthly cash flow trends, expenditure breakdowns by category, and live balance sheet summaries.
* **⚡ Dynamic Data Entry:** Seamlessly log expenditures, income, and investments with dynamic category fields that let you create new categories on the fly.

---

## 🛠️ Tech Stack

* **Frontend / UI:** [Streamlit](https://streamlit.io/) (Python web framework)
* **Backend & Analytics Engine:** Python (`pandas`, `numpy`)
* **Datastore:** Google Sheets API (`gspread` with Service Account auth)
* **Visualization:** [Plotly](https://plotly.com/python/) (Interactive, responsive charts)
* **Hosting:** Streamlit Community Cloud (Free Tier)

---

## 📁 Directory Structure

```text
finance-tracker/
├── .streamlit/
│   └── secrets.toml             # Local GCP service account secrets (ignored in git)
├── src/
│   ├── __init__.py
│   ├── config.py                # App configuration, profiles, default categories
│   ├── database.py              # Google Sheets API read/write integration (gspread)
│   ├── profile_selector.py      # Sidebar user switcher & session state management
│   ├── analytics.py             # Real-time financial calculations (pandas/numpy)
│   └── components/
│       ├── __init__.py
│       ├── forms.py             # Transaction, income, and investment entry forms
│       └── charts.py            # Responsive Plotly metrics & visual widgets
├── app.py                       # Main Streamlit application orchestrator
├── requirements.txt             # Python dependencies
├── SPEC.md                      # Detailed technical specification roadmap
└── README.md                    # Project documentation