from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CATEGORIES = [
    "Food",
    "Transport",
    "Shopping",
    "Bills",
    "Health",
    "Education",
    "Entertainment",
    "Travel",
    "Rent",
    "Other",
]


def _paths(data_dir: Path) -> tuple[Path, Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "expenses.json", data_dir / "budgets.json"


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        _atomic_write(path, default)
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        backup = path.with_suffix(path.suffix + ".corrupt")
        try:
            path.replace(backup)
        except OSError:
            pass
        _atomic_write(path, default)
        return default


def load_expenses(data_dir: Path) -> list[dict]:
    expenses_path, _ = _paths(data_dir)
    data = _read_json(expenses_path, [])
    if not isinstance(data, list):
        raise ValueError("expenses.json must contain a JSON array.")
    return data


def save_expenses(data_dir: Path, expenses: list[dict]) -> None:
    expenses_path, _ = _paths(data_dir)
    _atomic_write(expenses_path, expenses)


def load_budgets(data_dir: Path) -> dict[str, float]:
    _, budgets_path = _paths(data_dir)
    data = _read_json(budgets_path, {})
    if not isinstance(data, dict):
        raise ValueError("budgets.json must contain a JSON object.")
    clean = {}
    for key, value in data.items():
        try:
            clean[str(key)] = round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return clean


def save_budgets(data_dir: Path, budgets: dict[str, float]) -> None:
    _, budgets_path = _paths(data_dir)
    _atomic_write(budgets_path, budgets)


def validate_expense(expense: dict) -> None:
    required = ["id", "date", "category", "description", "amount", "payment_method"]
    missing = [field for field in required if field not in expense]
    if missing:
        raise ValueError(f"Missing expense fields: {', '.join(missing)}")
    if not str(expense["description"]).strip():
        raise ValueError("Description cannot be empty.")
    amount = float(expense["amount"])
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    datetime.fromisoformat(str(expense["date"]))


def add_expense(data_dir: Path, expense: dict) -> None:
    validate_expense(expense)
    expenses = load_expenses(data_dir)
    if any(item.get("id") == expense["id"] for item in expenses):
        raise ValueError("An expense with this ID already exists.")
    expense = dict(expense)
    expense.setdefault("notes", "")
    expense["amount"] = round(float(expense["amount"]), 2)
    expenses.append(expense)
    save_expenses(data_dir, expenses)


def update_expense(data_dir: Path, expense_id: str, changes: dict) -> bool:
    expenses = load_expenses(data_dir)
    for index, item in enumerate(expenses):
        if item.get("id") == expense_id:
            updated = dict(item)
            updated.update(changes)
            updated["id"] = expense_id
            validate_expense(updated)
            updated["amount"] = round(float(updated["amount"]), 2)
            expenses[index] = updated
            save_expenses(data_dir, expenses)
            return True
    return False


def delete_expense(data_dir: Path, expense_id: str) -> bool:
    expenses = load_expenses(data_dir)
    new_expenses = [item for item in expenses if item.get("id") != expense_id]
    changed = len(new_expenses) != len(expenses)
    if changed:
        save_expenses(data_dir, new_expenses)
    return changed


def add_or_update_budget(data_dir: Path, category: str, amount: float) -> None:
    if amount < 0:
        raise ValueError("Budget cannot be negative.")
    budgets = load_budgets(data_dir)
    budgets[category] = round(float(amount), 2)
    save_budgets(data_dir, budgets)


def export_bundle(data_dir: Path) -> bytes:
    bundle = {
        "format": "expense-tracker-json-backup",
        "version": 1,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "expenses": load_expenses(data_dir),
        "budgets": load_budgets(data_dir),
    }
    return json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8")


def import_bundle(data_dir: Path, raw: bytes) -> None:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Backup must be a JSON object.")
    expenses = payload.get("expenses")
    budgets = payload.get("budgets")
    if not isinstance(expenses, list) or not isinstance(budgets, dict):
        raise ValueError("Backup must contain 'expenses' array and 'budgets' object.")

    for expense in expenses:
        validate_expense(expense)

    clean_budgets = {}
    for category, amount in budgets.items():
        value = float(amount)
        if value < 0:
            raise ValueError("Budget cannot be negative.")
        clean_budgets[str(category)] = round(value, 2)

    save_expenses(data_dir, expenses)
    save_budgets(data_dir, clean_budgets)
