from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import plotly.express as px
import streamlit as st

from data_manager import (
    DEFAULT_CATEGORIES,
    add_expense,
    add_or_update_budget,
    delete_expense,
    export_bundle,
    import_bundle,
    load_budgets,
    load_expenses,
    save_budgets,
    update_expense,
)


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"

st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
        div[data-testid="stMetric"] {
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 12px;
            padding: 12px;
        }
        .small-note {font-size: .85rem; opacity: .75;}
        .danger-note {
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid rgba(255, 80, 80, .35);
            background: rgba(255, 80, 80, .06);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_state() -> None:
    defaults = {
        "expenses": load_expenses(DATA_DIR),
        "budgets": load_budgets(DATA_DIR),
        "page": "Dashboard",
        "edit_id": None,
        "form_nonce": 0,
        "flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh_data() -> None:
    st.session_state.expenses = load_expenses(DATA_DIR)
    st.session_state.budgets = load_budgets(DATA_DIR)


def set_flash(message: str, level: str = "success") -> None:
    st.session_state.flash = {"message": message, "level": level}


def show_flash() -> None:
    flash = st.session_state.get("flash")
    if not flash:
        return
    level = flash["level"]
    if level == "error":
        st.error(flash["message"])
    elif level == "warning":
        st.warning(flash["message"])
    elif level == "info":
        st.info(flash["message"])
    else:
        st.success(flash["message"])
    st.session_state.flash = None


def money(value: float) -> str:
    return f"₹{value:,.2f}"


def expenses_df(expenses: list[dict]) -> pd.DataFrame:
    columns = ["id", "date", "category", "description", "amount", "payment_method", "notes"]
    if not expenses:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(expenses)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df[columns].sort_values(["date", "id"], ascending=[False, False])


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    with st.sidebar:
        st.markdown("### Filters")
        min_date = df["date"].min().date()
        max_date = df["date"].max().date()
        selected_dates = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="filter_dates",
        )
        categories = sorted(df["category"].dropna().unique().tolist())
        selected_categories = st.multiselect(
            "Categories",
            categories,
            default=categories,
            key="filter_categories",
        )
        methods = sorted(df["payment_method"].dropna().unique().tolist())
        selected_methods = st.multiselect(
            "Payment methods",
            methods,
            default=methods,
            key="filter_methods",
        )
        search = st.text_input("Search", placeholder="Description or notes...", key="filter_search")

    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start, end = selected_dates
    else:
        start = end = selected_dates

    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    if selected_categories:
        mask &= df["category"].isin(selected_categories)
    else:
        mask &= False
    if selected_methods:
        mask &= df["payment_method"].isin(selected_methods)
    else:
        mask &= False
    if search.strip():
        term = search.strip().lower()
        mask &= (
            df["description"].fillna("").str.lower().str.contains(term, regex=False)
            | df["notes"].fillna("").str.lower().str.contains(term, regex=False)
        )
    return df.loc[mask].copy()


def dashboard() -> None:
    st.title("💰 Expense Tracker")
    st.caption("Local JSON-powered personal finance tracker built with Streamlit.")

    df = apply_filters(expenses_df(st.session_state.expenses))

    total = float(df["amount"].sum()) if not df.empty else 0.0
    count = int(len(df))
    average = total / count if count else 0.0

    today = date.today()
    month_start = today.replace(day=1)
    month_df = expenses_df(st.session_state.expenses)
    month_total = (
        float(month_df.loc[month_df["date"].dt.date >= month_start, "amount"].sum())
        if not month_df.empty
        else 0.0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filtered spending", money(total))
    c2.metric("Transactions", f"{count:,}")
    c3.metric("Average expense", money(average))
    c4.metric("This month", money(month_total))

    if df.empty:
        st.info("No expenses match the current filters. Use **Add Expense** to record your first transaction.")
        return

    left, right = st.columns(2)
    with left:
        cat = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
        fig = px.pie(cat, names="category", values="amount", hole=0.48, title="Spending by category")
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        daily = df.groupby("date", as_index=False)["amount"].sum()
        fig = px.line(daily, x="date", y="amount", markers=True, title="Spending trend")
        fig.update_yaxes(tickprefix="₹")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Recent expenses")
    recent = df.sort_values("date", ascending=False).head(8).copy()
    recent["date"] = recent["date"].dt.strftime("%d %b %Y")
    recent["amount"] = recent["amount"].map(money)
    st.dataframe(
        recent[["date", "category", "description", "amount", "payment_method"]],
        use_container_width=True,
        hide_index=True,
    )


def expense_form(existing: dict | None = None) -> None:
    is_edit = existing is not None
    st.subheader("Edit expense" if is_edit else "Add expense")

    key_suffix = f"_{existing['id']}" if is_edit else f"_{st.session_state.form_nonce}"
    initial_date = date.fromisoformat(existing["date"]) if is_edit else date.today()
    initial_category = existing["category"] if is_edit else DEFAULT_CATEGORIES[0]
    if initial_category not in DEFAULT_CATEGORIES:
        categories = DEFAULT_CATEGORIES + [initial_category]
    else:
        categories = DEFAULT_CATEGORIES

    with st.form(f"expense_form{key_suffix}", clear_on_submit=not is_edit):
        c1, c2, c3 = st.columns(3)
        with c1:
            expense_date = st.date_input("Date", value=initial_date, max_value=date.today())
        with c2:
            category = st.selectbox(
                "Category",
                categories,
                index=categories.index(initial_category),
            )
        with c3:
            amount = st.number_input(
                "Amount (₹)",
                min_value=0.01,
                value=float(existing["amount"]) if is_edit else 0.01,
                step=10.0,
                format="%.2f",
            )

        description = st.text_input(
            "Description",
            value=existing["description"] if is_edit else "",
            placeholder="e.g. Lunch, bus ticket, electricity bill",
        )
        c4, c5 = st.columns(2)
        with c4:
            methods = ["UPI", "Cash", "Debit Card", "Credit Card", "Bank Transfer", "Other"]
            current_method = existing["payment_method"] if is_edit else "UPI"
            payment_method = st.selectbox(
                "Payment method",
                methods,
                index=methods.index(current_method) if current_method in methods else len(methods) - 1,
            )
        with c5:
            notes = st.text_input("Notes (optional)", value=existing["notes"] if is_edit else "")

        submitted = st.form_submit_button(
            "Update expense" if is_edit else "Add expense",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        description = description.strip()
        if not description:
            st.error("Description is required.")
            return
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return

        payload = {
            "date": expense_date.isoformat(),
            "category": category,
            "description": description,
            "amount": round(float(amount), 2),
            "payment_method": payment_method,
            "notes": notes.strip(),
        }

        try:
            if is_edit:
                updated = update_expense(DATA_DIR, existing["id"], payload)
                if not updated:
                    raise ValueError("Expense no longer exists.")
                st.session_state.edit_id = None
                set_flash("Expense updated successfully.")
            else:
                payload["id"] = uuid4().hex
                payload["created_at"] = datetime.now().isoformat(timespec="seconds")
                add_expense(DATA_DIR, payload)
                st.session_state.form_nonce += 1
                set_flash("Expense added successfully.")
            refresh_data()
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(f"Could not save the expense: {exc}")


def add_expense_page() -> None:
    st.title("➕ Add Expense")
    expense_form()


def manage_expenses() -> None:
    st.title("🧾 Manage Expenses")
    df = expenses_df(st.session_state.expenses)
    filtered = apply_filters(df)

    if filtered.empty:
        st.info("No expenses match the current filters.")
        return

    st.caption(f"{len(filtered)} expense(s) shown.")
    display = filtered.copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    display["amount"] = display["amount"].map(money)

    st.dataframe(
        display[["id", "date", "category", "description", "amount", "payment_method", "notes"]],
        use_container_width=True,
        hide_index=True,
        column_config={"id": None},
    )

    st.subheader("Update or delete")
    options = filtered["id"].tolist()
    labels = {
        row["id"]: f"{row['date'].strftime('%d %b %Y')} • {row['description']} • {money(row['amount'])}"
        for _, row in filtered.iterrows()
    }
    selected_id = st.selectbox("Select an expense", options, format_func=lambda x: labels[x])

    selected = next((e for e in st.session_state.expenses if e["id"] == selected_id), None)
    if selected:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("✏️ Edit selected", use_container_width=True):
                st.session_state.edit_id = selected_id
                st.rerun()
        with b2:
            if st.button("🗑️ Delete selected", type="secondary", use_container_width=True):
                st.session_state[f"confirm_delete_{selected_id}"] = True

        if st.session_state.get(f"confirm_delete_{selected_id}", False):
            st.warning("This action permanently removes the selected record from the JSON file.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Confirm delete", type="primary", use_container_width=True):
                    try:
                        delete_expense(DATA_DIR, selected_id)
                        st.session_state[f"confirm_delete_{selected_id}"] = False
                        set_flash("Expense deleted.")
                        refresh_data()
                        st.rerun()
                    except OSError as exc:
                        st.error(f"Delete failed: {exc}")
            with c2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state[f"confirm_delete_{selected_id}"] = False
                    st.rerun()

    if st.session_state.edit_id:
        edit_item = next((e for e in st.session_state.expenses if e["id"] == st.session_state.edit_id), None)
        if edit_item:
            st.divider()
            expense_form(edit_item)
        else:
            st.session_state.edit_id = None


def analytics_page() -> None:
    st.title("📊 Analytics")
    df = apply_filters(expenses_df(st.session_state.expenses))
    if df.empty:
        st.info("Add expenses to unlock analytics.")
        return

    c1, c2 = st.columns(2)
    with c1:
        category = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
        fig = px.bar(category, x="category", y="amount", text_auto=".2s", title="Category totals")
        fig.update_yaxes(tickprefix="₹")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        method = df.groupby("payment_method", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
        fig = px.bar(method, x="payment_method", y="amount", text_auto=".2s", title="Payment method totals")
        fig.update_yaxes(tickprefix="₹")
        st.plotly_chart(fig, use_container_width=True)

    monthly = df.copy()
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
    monthly = monthly.groupby("month", as_index=False)["amount"].sum()
    fig = px.area(monthly, x="month", y="amount", markers=True, title="Monthly spending")
    fig.update_yaxes(tickprefix="₹")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top spending categories")
    top = category.head(5).copy()
    top["share"] = (top["amount"] / top["amount"].sum() * 100).round(1)
    top["amount"] = top["amount"].map(money)
    top["share"] = top["share"].map(lambda x: f"{x:.1f}%")
    st.dataframe(top.rename(columns={"amount": "Total", "share": "Share"}), use_container_width=True, hide_index=True)


def budgets_page() -> None:
    st.title("🎯 Budgets")
    st.caption("Set a monthly limit by category. Budget values are stored in budgets.json.")

    with st.form("budget_form"):
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox("Category", DEFAULT_CATEGORIES)
        with c2:
            amount = st.number_input("Monthly budget (₹)", min_value=0.0, value=5000.0, step=500.0)
        save = st.form_submit_button("Save budget", type="primary", use_container_width=True)

    if save:
        try:
            add_or_update_budget(DATA_DIR, category, round(float(amount), 2))
            refresh_data()
            set_flash(f"Budget saved for {category}.")
            st.rerun()
        except OSError as exc:
            st.error(f"Could not save budget: {exc}")

    df = expenses_df(st.session_state.expenses)
    month_start = date.today().replace(day=1)
    current_month = (
        df[df["date"].dt.date >= month_start]
        if not df.empty
        else pd.DataFrame(columns=df.columns)
    )
    spending = current_month.groupby("category")["amount"].sum().to_dict() if not current_month.empty else {}

    rows = []
    for category_name, budget in st.session_state.budgets.items():
        spent = float(spending.get(category_name, 0.0))
        pct = (spent / budget * 100) if budget > 0 else 0.0
        rows.append({
            "Category": category_name,
            "Budget": budget,
            "Spent": spent,
            "Remaining": budget - spent,
            "Usage": min(pct, 100),
        })

    if not rows:
        st.info("No budgets configured yet.")
        return

    budget_df = pd.DataFrame(rows)
    for _, row in budget_df.iterrows():
        cols = st.columns([2, 1, 1, 1])
        cols[0].write(f"**{row['Category']}**")
        cols[1].write(f"Budget: {money(row['Budget'])}")
        cols[2].write(f"Spent: {money(row['Spent'])}")
        cols[3].write(f"Remaining: {money(row['Remaining'])}")
        st.progress(int(row["Usage"]))
        if row["Spent"] > row["Budget"]:
            st.error(f"{row['Category']}: budget exceeded by {money(row['Spent'] - row['Budget'])}.")
        elif row["Usage"] >= 80:
            st.warning(f"{row['Category']}: {row['Usage']:.0f}% of budget used.")
        else:
            st.success(f"{row['Category']}: {row['Usage']:.0f}% used.")


def backup_page() -> None:
    st.title("⚙️ Backup & Settings")
    st.markdown(
        '<div class="danger-note"><b>Important:</b> JSON storage is intentionally used instead of a database. '
        'On hosted environments, local filesystem changes may not survive app restarts/redeployments. '
        'Use the backup download regularly if you deploy this version to Community Cloud.</div>',
        unsafe_allow_html=True,
    )

    bundle = export_bundle(DATA_DIR)
    st.download_button(
        "⬇️ Download full JSON backup",
        data=bundle,
        file_name=f"expense_tracker_backup_{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.subheader("Restore backup")
    uploaded = st.file_uploader("Upload a backup JSON file", type=["json"])
    if uploaded is not None:
        if st.button("Restore uploaded backup", type="primary"):
            try:
                import_bundle(DATA_DIR, uploaded.getvalue())
                refresh_data()
                st.session_state.edit_id = None
                set_flash("Backup restored successfully.")
                st.rerun()
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                st.error(f"Restore failed: {exc}")

    st.divider()
    st.subheader("Data summary")
    st.write(f"Expenses stored: **{len(st.session_state.expenses)}**")
    st.write(f"Budget categories configured: **{len(st.session_state.budgets)}**")

    if st.button("Reset all data", type="secondary"):
        st.session_state["confirm_reset"] = True

    if st.session_state.get("confirm_reset"):
        st.warning("Reset deletes all expenses and budgets from the local JSON files.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm reset", type="primary", use_container_width=True):
                save_budgets(DATA_DIR, {})
                from data_manager import save_expenses
                save_expenses(DATA_DIR, [])
                refresh_data()
                st.session_state.confirm_reset = False
                set_flash("All data has been reset.", "warning")
                st.rerun()
        with c2:
            if st.button("Cancel reset", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()


def sidebar() -> None:
    st.sidebar.title("💰 Expense Tracker")
    st.sidebar.caption("JSON storage • CRUD • Session State • Analytics")

    pages = ["Dashboard", "Add Expense", "Manage Expenses", "Analytics", "Budgets", "Backup & Settings"]
    selected = st.sidebar.radio("Navigation", pages, index=pages.index(st.session_state.page))
    if selected != st.session_state.page:
        st.session_state.page = selected
        st.session_state.edit_id = None

    st.sidebar.divider()
    st.sidebar.caption("Tip: export a backup before major changes.")


init_state()
sidebar()
show_flash()

page = st.session_state.page

if page == "Dashboard":
    dashboard()
elif page == "Add Expense":
    add_expense_page()
elif page == "Manage Expenses":
    manage_expenses()
elif page == "Analytics":
    analytics_page()
elif page == "Budgets":
    budgets_page()
elif page == "Backup & Settings":
    backup_page()
