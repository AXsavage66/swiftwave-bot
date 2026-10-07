from database import engine, SessionLocal, Base
from models import User, Order, Transaction
import uuid

# 1. Create tables in swiftwave.db if they don't exist
Base.metadata.create_all(bind=engine)

def run_local_test():
    db = SessionLocal()
    test_phone = "2348012345678"

    print("🛠️ Testing Local Database Setup...")

    # Step A: Register or fetch user
    user = db.query(User).filter(User.phone_number == test_phone).first()
    if not user:
        print(f"Creating test user with phone: {test_phone}")
        user = User(phone_number=test_phone, name="Test Customer", wallet_balance=2000.0)
        db.add(user)
        db.commit()
        db.refresh(user)

    print(f"👤 User: {user.name} | Wallet Balance: ₦{user.wallet_balance}")

    # Step B: Simulate purchasing MTN 1GB (Wholesale: ₦570, Retail: ₦800)
    selling_price = 800.0
    cost_price = 570.0
    net_profit = selling_price - cost_price

    if user.wallet_balance < selling_price:
        print("❌ Insufficient funds!")
        db.close()
        return

    # Step C: Deduct wallet & Record Transaction
    bal_before = user.wallet_balance
    user.wallet_balance -= selling_price
    bal_after = user.wallet_balance

    txn = Transaction(
        user_phone=user.phone_number,
        transaction_type="DEBIT",
        amount=selling_price,
        balance_before=bal_before,
        balance_after=bal_after,
        reference=f"TXN_{uuid.uuid4().hex[:8].upper()}"
    )
    db.add(txn)

    # Step D: Log Order
    order = Order(
        user_phone=user.phone_number,
        service_type="DATA",
        network="MTN",
        plan_id=46,  # 1GB SME 30 Days
        recipient_phone="08012345678",
        cost_price=cost_price,
        selling_price=selling_price,
        profit=net_profit,
        status="SUCCESS",
        external_ref="MOCK_AGGREGATOR_REF_101"
    )
    db.add(order)

    # Commit all changes atomically
    db.commit()

    print(f"✅ Purchase Simulated Successfully!")
    print(f"📉 New Balance: ₦{bal_after}")
    print(f"💰 Profit Generated: ₦{net_profit}")
    db.close()

if __name__ == "__main__":
    run_local_test()