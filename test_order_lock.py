import threading
from database import SessionLocal
from models import User
from services.order_service import OrderService

def make_purchase(thread_id: int):
    db = SessionLocal()
    order_svc = OrderService(db)
    print(f"Thread {thread_id} attempting order...")
    res = order_svc.process_data_order(
        buyer_phone="2348000000000",
        network="MTN",
        plan_id=43,
        recipient_phone="07046470954",
        cost_price=99.0,
        retail_price=150.0
    )
    print(f"Thread {thread_id} result: {res['message']}")
    db.close()

# Simulate two simultaneous clicks at the exact same millisecond
t1 = threading.Thread(target=make_purchase, args=(1,))
t2 = threading.Thread(target=make_purchase, args=(2,))

t1.start()
t2.start()

t1.join()
t2.join()