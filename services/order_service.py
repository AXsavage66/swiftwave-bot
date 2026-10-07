import time
import threading
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import User, Order, Transaction
from services.cheapdatahub import CheapDataHubService


class OrderLockManager:
    """
    Thread-safe concurrency lock and idempotency filter.
    Prevents race conditions, double-charging, and rapid repeat submissions.
    """
    def __init__(self, cooldown_seconds: int = 15):
        self._lock = threading.Lock()
        self._active_users: Dict[str, float] = {}  # {buyer_phone: start_time}
        self._recent_orders: Dict[str, float] = {}  # {order_fingerprint: completed_time}
        self.cooldown_seconds = cooldown_seconds

    def acquire_lock(self, buyer_phone: str, recipient_phone: str, plan_id: int) -> Dict[str, Any]:
        """
        Attempts to acquire an execution lock for the transaction.
        Returns {'allowed': True} or {'allowed': False, 'reason': ...}.
        """
        with self._lock:
            now = time.time()
            fingerprint = f"{buyer_phone}:{recipient_phone}:{plan_id}"

            # 1. Check if user already has an in-flight order
            if buyer_phone in self._active_users:
                elapsed = now - self._active_users[buyer_phone]
                if elapsed < 60:  # 60s hard ceiling to prevent permanent locks on hard crashes
                    return {
                        "allowed": False,
                        "reason": "⏳ An order is currently processing for your account. Please wait a moment."
                    }
                else:
                    # Stale lock cleanup
                    del self._active_users[buyer_phone]

            # 2. Check for duplicate order within cooldown window
            last_timestamp = self._recent_orders.get(fingerprint)
            if last_timestamp and (now - last_timestamp) < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - (now - last_timestamp))
                return {
                    "allowed": False,
                    "reason": f"⚠️ Duplicate request detected! An identical bundle was just ordered for this number. Please wait {remaining}s before retrying."
                }

            # 3. Grant lock
            self._active_users[buyer_phone] = now
            return {"allowed": True}

    def release_lock(self, buyer_phone: str, recipient_phone: str, plan_id: int):
        """Releases active lock and records completion timestamp."""
        with self._lock:
            fingerprint = f"{buyer_phone}:{recipient_phone}:{plan_id}"
            self._active_users.pop(buyer_phone, None)
            self._recent_orders[fingerprint] = time.time()

            # Evict entries older than 5 minutes to prevent memory leak
            cutoff = time.time() - 300
            self._recent_orders = {
                k: v for k, v in self._recent_orders.items() if v > cutoff
            }


# Singleton lock manager instance across the application lifetime
GLOBAL_ORDER_LOCK = OrderLockManager(cooldown_seconds=15)


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.vtu_provider = CheapDataHubService()

    def process_data_order(
        self,
        buyer_phone: str,
        network: str,
        plan_id: int,
        recipient_phone: str,
        cost_price: float,
        retail_price: float
    ) -> Dict[str, Any]:
        """
        Executes data bundle purchase with concurrency guards and atomic state updates.
        """
        # Step 1: Concurrency and Idempotency Guard
        lock_status = GLOBAL_ORDER_LOCK.acquire_lock(buyer_phone, recipient_phone, plan_id)
        if not lock_status["allowed"]:
            return {
                "success": False,
                "message": lock_status["reason"]
            }

        try:
            # Step 2: Fetch user and check balance
            user = self.db.query(User).filter(User.phone_number == buyer_phone).first()
            if not user:
                return {"success": False, "message": "User account not found."}

            if user.wallet_balance < retail_price:
                return {
                    "success": False,
                    "message": (
                        f"Insufficient balance. Cost is ₦{retail_price:,.2f}, "
                        f"but your wallet balance is ₦{user.wallet_balance:,.2f}."
                    )
                }

            # Step 3: Dispatch API call to CheapDataHub
            print(f"📡 [LOCK SECURED] Dispatching {network.upper()} plan {plan_id} to {recipient_phone}...")
            vtu_response = self.vtu_provider.buy_data(
                network=network,
                plan_id=plan_id,
                phone_number=recipient_phone
            )

            # Step 4: Handle Telco / Provider Rejection
            if not vtu_response.get("success"):
                err_msg = vtu_response.get("error", "Data Purchase Failed")
                print(f"❌ VTU Order Rejected by Provider: {err_msg}")
                return {
                    "success": False,
                    "message": f"Order failed: {err_msg}. Your wallet was NOT charged."
                }

            # Step 5: Atomically Deduct Funds and Log Profit
            profit = retail_price - cost_price
            user.wallet_balance -= retail_price

            new_order = Order(
                user_id=user.id,
                network=network.upper(),
                recipient_phone=recipient_phone,
                plan_id=str(plan_id),
                cost_price=cost_price,
                selling_price=retail_price,
                profit=profit,
                status="SUCCESS",
                external_ref=vtu_response.get("reference", "N/A")
            )
            self.db.add(new_order)
            self.db.flush()

            # Record ledger audit transaction
            txn = Transaction(
                user_id=user.id,
                amount=retail_price,
                type="DEBIT",
                description=f"Purchase {network.upper()} plan {plan_id} for {recipient_phone}",
                reference=f"SW-ORD-{new_order.id}"
            )
            self.db.add(txn)
            self.db.commit()

            return {
                "success": True,
                "message": f"Success! ₦{retail_price:,.2f} deducted. Data delivered to {recipient_phone}.",
                "balance": user.wallet_balance,
                "reference": new_order.external_ref
            }

        except Exception as e:
            self.db.rollback()
            print(f"🚨 Transaction rollback due to error: {e}")
            return {
                "success": False,
                "message": "A critical system error occurred. Your wallet was NOT charged."
            }

        finally:
            # Step 6: Guarantee Lock Release
            GLOBAL_ORDER_LOCK.release_lock(buyer_phone, recipient_phone, plan_id)