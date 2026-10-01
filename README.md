# 💰 Expense Tracker — Streamlit + Local JSON

A complete personal Expense Tracker built with Python and Streamlit.

## Core requirements implemented

- Session state management with `st.session_state`
- Full CRUD:
  - Create expenses
  - Read/filter expenses
  - Update expenses
  - Delete expenses
- Interactive Plotly charts
- Local JSON storage — no SQL/NoSQL database
- Monthly category budgets
- Search and filters
- Payment-method analytics
- Monthly spending trend
- Backup and restore using one JSON file
- Atomic JSON writes to reduce the risk of partially written files
- Input validation
- Delete/reset confirmation
- Responsive Streamlit layout
- Community Cloud-ready structure

## Project structure

```text
expense_tracker_streamlit/
├── app.py
├── data_manager.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
└── data/
    ├── expenses.json
    └── budgets.json
```

## Run locally

Use Python 3.12 for a close match to the current Streamlit Community Cloud default.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start:

```bash
streamlit run app.py
```

Open the local URL shown by Streamlit.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload the entire project folder.
3. Sign in to Streamlit Community Cloud.
4. Connect GitHub.
5. Create an app.
6. Select the repository and branch.
7. Set the main file to `app.py`.
8. Deploy.

`requirements.txt` is in the repository root, so Community Cloud can install the required packages.

## Important JSON-storage limitation

This project intentionally does not use a traditional database. On a hosted service, local filesystem writes should not be treated as durable cloud storage. A restart, redeploy, or environment replacement can cause locally written JSON data to disappear.

For a student/demo/project deployment, use the **Backup & Settings → Download full JSON backup** feature regularly.

For a production multi-user application, replace the JSON storage layer with durable storage such as PostgreSQL, SQLite on a persistent volume, or a managed cloud database.

## Data model

### expenses.json

Each expense contains:

- `id`
- `date`
- `category`
- `description`
- `amount`
- `payment_method`
- `notes`
- `created_at`

### budgets.json

A JSON object maps a category to its monthly budget.

Example:

```json
{
  "Food": 5000,
  "Transport": 2500
}
```

## Architecture

```text
Streamlit UI
    │
    ├── Session State
    │      ├── current page
    │      ├── loaded expenses
    │      ├── loaded budgets
    │      ├── edit selection
    │      └── UI confirmations
    │
    ├── data_manager.py
    │      ├── validation
    │      ├── CRUD operations
    │      ├── atomic JSON writes
    │      └── backup/restore
    │
    └── data/
           ├── expenses.json
           └── budgets.json
```
