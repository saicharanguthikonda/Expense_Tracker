"""Small dependency-light smoke tests for the JSON data layer."""
from pathlib import Path
import tempfile

from data_manager import (
    add_expense,
    add_or_update_budget,
    delete_expense,
    export_bundle,
    import_bundle,
    load_budgets,
    load_expenses,
    update_expense,
)


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        expense = {
            "id": "test-1",
            "date": "2026-10-01",
            "category": "Food",
            "description": "Lunch",
            "amount": 120.50,
            "payment_method": "UPI",
            "notes": "Test record",
        }

        assert load_expenses(data_dir) == []
        add_expense(data_dir, expense)
        assert len(load_expenses(data_dir)) == 1

        assert update_expense(data_dir, "test-1", {"amount": 150})
        assert load_expenses(data_dir)[0]["amount"] == 150.0

        add_or_update_budget(data_dir, "Food", 5000)
        assert load_budgets(data_dir)["Food"] == 5000.0

        backup = export_bundle(data_dir)
        assert b'"expenses"' in backup

        delete_expense(data_dir, "test-1")
        assert load_expenses(data_dir) == []

        import_bundle(data_dir, backup)
        assert len(load_expenses(data_dir)) == 1
        assert load_budgets(data_dir)["Food"] == 5000.0

    print("All JSON data-layer smoke tests passed.")


if __name__ == "__main__":
    run()
