import os
import time
import random
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
        self._active_users: Dict[str, float] = {}
        self._recent_orders: Dict[str, float] = {}
        self.cooldown_seconds = cooldown_seconds

    def acquire_lock(self, buyer_phone: str, recipient_phone: str, plan_id: int) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            fingerprint = f"{buyer_phone}:{recipient_phone}:{plan_id}"

            if buyer_phone in self._active_users:
                elapsed = now - self._active_users[buyer_phone]
                if elapsed < 60:
                    return {
                        "allowed": False,
                        "reason": "⏳ An order is currently processing for your account. Please wait a moment."
                    }
                else:
                    del self._active_users[buyer_phone]

            last_timestamp = self._recent_orders.get(fingerprint)
            if last_timestamp and (now - last_timestamp) < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - (now - last_timestamp))
                return {
                    "allowed": False,
                    "reason": f"⚠️ Duplicate request detected! An identical order was just completed. Please wait {remaining}s."
                }

            self._active_users[buyer_phone] = now
            return {"allowed": True}

    def release_lock(self, buyer_phone: str, recipient_phone: str, plan_id: int):
        with self._lock:
            fingerprint = f"{buyer_phone}:{recipient_phone}:{plan_id}"
            self._active_users.pop(buyer_phone, None)
            self._recent_orders[fingerprint] = time.time()

            cutoff = time.time() - 300
            self._recent_orders = {
                k: v for k, v in self._recent_orders.items() if v > cutoff
            }


GLOBAL_ORDER_LOCK = OrderLockManager(cooldown_seconds=15)


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.vtu_provider = CheapDataHubService()
        self.mock_mode = os.getenv("MOCK_VTU", "true").lower() != "false"

    def process_data_order(
        self,
        buyer_phone: str,
        network: str,
        plan_id: int,
        recipient_phone: str,
        cost_price: float,
        retail_price: float,
        plan_name: str = ""
    ) -> Dict[str, Any]:
        """
        Executes Data, TalkMore Voice Minutes, Airtime, or Exam PIN orders
        with atomic wallet deduction and 1.5% Halal Cashback (Hibah).
        """
        lock_status = GLOBAL_ORDER_LOCK.acquire_lock(buyer_phone, recipient_phone, plan_id)
        if not lock_status["allowed"]:
            return {"success": False, "message": lock_status["reason"]}

        try:
            user = self.db.query(User).filter(User.phone_number == buyer_phone).first()
            if not user:
                return {"success": False, "message": "User account not found."}

            if user.wallet_balance < retail_price:
                return {
                    "success": False,
                    "message": (
                        f"❌ *Insufficient Wallet Balance*\n"
                        f"• Order Cost: *₦{retail_price:,.0f}*\n"
                        f"• Your Balance: *₦{user.wallet_balance:,.2f}*\n\n"
                        f"💡 _Reply *'fund 5000'* to add test funds in simulator mode._"
                    )
                }

            is_exam = plan_id in (801, 802, 803)
            is_talkmore = 900 <= plan_id <= 909
            is_airtime = plan_id == 999

            # Dispatch or Simulate VTU Fulfillment
            if self.mock_mode or is_exam or is_talkmore or is_airtime:
                if is_exam:
                    generated_pin = "".join([str(random.randint(0, 9)) for _ in range(12)])
                    serial_no = f"WRN{random.randint(10000000, 99999999)}"
                    vtu_response = {
                        "success": True,
                        "reference": f"PIN:{generated_pin}|SN:{serial_no}"
                    }
                else:
                    vtu_response = {
                        "success": True,
                        "reference": f"SW-{network.upper()}-{int(time.time())}"
                    }
            else:
                vtu_response = self.vtu_provider.buy_data(
                    network=network,
                    plan_id=plan_id,
                    phone_number=recipient_phone
                )

            if not vtu_response.get("success"):
                err_msg = vtu_response.get("error", "Provider Rejection")
                return {
                    "success": False,
                    "message": f"❌ Order failed: {err_msg}. Your wallet was NOT charged."
                }

            # Deduct retail price & grant 1.5% Halal Promotional Cashback (Hibah)
            cashback_earned = round(retail_price * 0.015, 2)
            profit = retail_price - cost_price - cashback_earned
            user.wallet_balance = round(user.wallet_balance - retail_price + cashback_earned, 2)

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

            txn = Transaction(
                user_id=user.id,
                amount=retail_price,
                type="DEBIT",
                description=f"{network.upper()} {plan_name or f'Plan {plan_id}'} for {recipient_phone}",
                reference=f"SW-ORD-{new_order.id}-{int(time.time())}"
            )
            self.db.add(txn)

            if cashback_earned > 0:
                cb_txn = Transaction(
                    user_id=user.id,
                    amount=cashback_earned,
                    type="CREDIT",
                    description=f"1.5% Instant Cashback Reward on Order #{new_order.id}",
                    reference=f"SW-CB-{new_order.id}-{int(time.time())}"
                )
                self.db.add(cb_txn)

            self.db.commit()

            # Format Specialized Receipt for Exam PINs vs. Telecom Orders
            if is_exam:
                ref_parts = new_order.external_ref.split("|")
                pin_code = ref_parts[0].replace("PIN:", "")
                serial_code = ref_parts[1].replace("SN:", "") if len(ref_parts) > 1 else "N/A"
                return {
                    "success": True,
                    "message": (
                        f"🎓 *{network.upper()} Result Checker PIN Generated!*\n\n"
                        f"• *PIN:* `{pin_code}`\n"
                        f"• *Serial No:* `{serial_code}`\n"
                        f"• *Amount Charged:* ₦{retail_price:,.0f}\n"
                        f"• *Instant Cashback Added:* +₦{cashback_earned:,.2f} 🎁\n"
                        f"• *New Wallet Balance:* ₦{user.wallet_balance:,.2f}\n\n"
                        f"🔒 _Saved to your PIN Vault! Type *'my pins'* anytime to view it again._"
                    )
                }

            service_label = (
                f"TalkMore Voice Bundle ({plan_name})" if is_talkmore
                else (f"Airtime Top-Up (₦{retail_price:,.0f})" if is_airtime else (plan_name or f"Plan #{plan_id}"))
            )

            return {
                "success": True,
                "message": (
                    f"✅ *Transaction Successful!*\n\n"
                    f"• *Service:* {network.upper()} — {service_label}\n"
                    f"• *Recipient:* {recipient_phone}\n"
                    f"• *Amount Charged:* ₦{retail_price:,.0f}\n"
                    f"• *Instant Cashback Added:* +₦{cashback_earned:,.2f} 🎁\n"
                    f"• *New Wallet Balance:* ₦{user.wallet_balance:,.2f}\n"
                    f"• *Ref:* `{new_order.external_ref}`"
                ),
                "balance": user.wallet_balance,
                "reference": new_order.external_ref
            }

        except Exception as e:
            self.db.rollback()
            print(f"🚨 Transaction rollback due to error: {e}")
            return {
                "success": False,
                "message": "🚨 A system error occurred. Your wallet was NOT charged."
            }

        finally:
            GLOBAL_ORDER_LOCK.release_lock(buyer_phone, recipient_phone, plan_id)