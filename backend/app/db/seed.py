
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.db.database import SessionLocal
from app.db.models import DemoTransaction


DEMO_TRANSACTIONS = [
    {
        "reference_norm": "DEMO123456",
        "amount": 500.00,
        "currency": "INR",
        "payee_alias": "Demo Merchant",
        "transaction_time": datetime(
            2026, 10, 15, 10, 30, tzinfo=timezone.utc
        ),
        "seeded_status": "SUCCESS",
    },
    {
        "reference_norm": "DEMO789012",
        "amount": 250.00,
        "currency": "INR",
        "payee_alias": "Sample Store",
        "transaction_time": datetime(
            2026, 10, 15, 11, 0, tzinfo=timezone.utc
        ),
        "seeded_status": "SUCCESS",
    },
    {
        "reference_norm": "DEMO345678",
        "amount": 1200.00,
        "currency": "INR",
        "payee_alias": "Test Cafe",
        "transaction_time": datetime(
            2026, 10, 15, 12, 15, tzinfo=timezone.utc
        ),
        "seeded_status": "SUCCESS",
    },
]


def seed_demo_transactions():
    with SessionLocal() as session:
        statement = insert(DemoTransaction).values(DEMO_TRANSACTIONS)
        statement = statement.on_conflict_do_nothing(
            index_elements=["reference_norm"]
        )
        session.execute(statement)
        session.commit()

    print("Demo transactions seeded successfully.")


if __name__ == "__main__":
    seed_demo_transactions()
