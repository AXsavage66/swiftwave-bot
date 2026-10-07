from database import SessionLocal
from models import User
from services.order_service import OrderService

db = SessionLocal()
order_service = OrderService(db)

# 1. Buyer account in your local database
buyer_phone = "2348000000000"
user = db.query(User).filter(User.phone_number == buyer_phone).first()
if not user:
    user = User(phone_number=buyer_phone, name="Mukhtar Giwa", wallet_balance=2000.0)
    db.add(user)
    db.commit()

# 2. Put a REAL, active MTN phone number here to receive the data
RECEIVER_PHONE = "07046470954"  # <-- PUT AN ACTIVE MTN NUMBER HERE

print(f"User Balance Before: ₦{user.wallet_balance}")

# Test with Plan ID 43 (MTN 110MB - Wholesale ₦99, Retail ₦150)
result = order_service.process_data_order(
    buyer_phone=buyer_phone,
    network="mtn",
    plan_id=43,
    recipient_phone=RECEIVER_PHONE,
    cost_price=99.0,
    retail_price=150.0
)

print("\n--- ORDER RESULT ---")
print(result)

db.close()