from datetime import date

from app.db.database import SessionLocal
from app.db.models.order import Order


def seed_orders():
    orders = [
        Order(order_date=date(2026, 7, 1), customer_name="Acme Corp", total_amount=1200.50, status="completed"),
        Order(order_date=date(2026, 7, 2), customer_name="Beta LLC", total_amount=750.00, status="completed"),
        Order(order_date=date(2026, 7, 2), customer_name="Acme Corp", total_amount=240.00, status="completed"),
        Order(order_date=date(2026, 7, 3), customer_name="Delta Inc", total_amount=1830.90, status="completed"),
        Order(order_date=date(2026, 7, 5), customer_name="Echo Co", total_amount=520.45, status="completed"),
        Order(order_date=date(2026, 7, 6), customer_name="Beta LLC", total_amount=330.00, status="completed"),
    ]

    db = SessionLocal()
    try:
        db.add_all(orders)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_orders()
    print("Seeded orders.")
