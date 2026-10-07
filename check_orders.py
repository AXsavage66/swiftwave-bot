from database import SessionLocal
from models import Order, Transaction

db = SessionLocal()

# Query the most recent order logged in swiftwave.db
latest_order = db.query(Order).order_by(Order.id.desc()).first()

if latest_order:
    print("\n==============================")
    print("      LATEST VTU ORDER        ")
    print("==============================")
    print(f"Network:          {latest_order.network}")
    print(f"Recipient:        {latest_order.recipient_phone}")
    print(f"Wholesale Cost:   ₦{latest_order.cost_price:.2f}")
    print(f"Retail Price:     ₦{latest_order.selling_price:.2f}")
    print(f"Net Profit:       ₦{latest_order.profit:.2f}")
    print(f"Status:           {latest_order.status}")
    print(f"Transaction Ref:  {latest_order.external_ref}")
    print("==============================\n")
else:
    print("No orders found in the database.")

db.close()