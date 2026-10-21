import os
import re
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from sqlalchemy.orm import Session

from models import User, SavedContact, PendingOrder, Transaction, Order
from services.catalog import (
    DATA_CATALOG,
    TALKMORE_CATALOG,
    EXAM_CATALOG,
    format_menu_text,
    format_talkmore_menu,
    get_plan_by_id
)
from services.order_service import OrderService

PREFIX_MAP = {
    "MTN": {"0803", "0806", "0703", "0706", "0813", "0816", "0810", "0814", "0903", "0906", "0913", "0916", "0704"},
    "AIRTEL": {"0802", "0808", "0708", "0812", "0701", "0902", "0901", "0904", "0907", "0912"},
    "GLO": {"0805", "0807", "0705", "0815", "0811", "0905", "0915"},
    "9MOBILE": {"0809", "0818", "0817", "0909", "0908"}
}

CONV_CONTEXT: Dict[str, Dict[str, Any]] = {}


def get_conv_context(sender_phone: str) -> Dict[str, Any]:
    ctx = CONV_CONTEXT.get(sender_phone)
    if not ctx:
        return {}
    if time.time() - ctx.get("updated_at", 0) > 600:
        CONV_CONTEXT.pop(sender_phone, None)
        return {}
    return ctx


def set_conv_context(sender_phone: str, **kwargs):
    ctx = get_conv_context(sender_phone)
    ctx.update(kwargs)
    ctx["updated_at"] = time.time()
    CONV_CONTEXT[sender_phone] = ctx


def clear_conv_context(sender_phone: str):
    CONV_CONTEXT.pop(sender_phone, None)


def normalize_ng_phone(raw_phone: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw_phone or "")
    if len(digits) == 11 and digits.startswith("0"):
        return digits
    if len(digits) == 13 and digits.startswith("234"):
        return "0" + digits[3:]
    if len(digits) == 10 and digits[0] in ("7", "8", "9"):
        return "0" + digits
    return None


def detect_network_from_phone(phone_11: str) -> Optional[str]:
    if not phone_11 or len(phone_11) < 4:
        return None
    prefix = phone_11[:4]
    for net, prefixes in PREFIX_MAP.items():
        if prefix in prefixes:
            return net
    return None


def get_or_create_user(db: Session, sender_phone: str, profile_name: str = "Boss") -> User:
    user = db.query(User).filter(User.phone_number == sender_phone).first()
    if not user:
        clean_digits = re.sub(r"\D", "", sender_phone)[-8:].zfill(8)
        user = User(
            phone_number=sender_phone,
            name=profile_name,
            wallet_balance=0.0,
            bank_name="Monnify / PalmPay (Swiftwave)",
            account_number="90" + clean_digits,
            account_name="SWIFTWAVE / CUSTOMER",
            tracking_reference=f"SW-REF-{clean_digits[-6:]}"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user.name in ["Valued Customer", "Boss"] and profile_name not in ["Valued Customer", "Boss"]:
            user.name = profile_name
            db.commit()
    return user


def get_all_catalog_plans(network: Optional[str] = None) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    if network:
        net_dict = DATA_CATALOG.get(network.upper(), {})
        for k, v in net_dict.items():
            plans.append({"key": k, "network": network.upper(), **v})
    else:
        for net, net_dict in DATA_CATALOG.items():
            for k, v in net_dict.items():
                plans.append({"key": k, "network": net.upper(), **v})
    return plans


def filter_plans_by_attributes(plans: List[Dict[str, Any]], query_text: str, strict: bool = False) -> List[Dict[str, Any]]:
    q = query_text.lower()
    results = list(plans)

    size_match = re.search(r"(\d+(?:\.\d+)?\s*(?:gb|mb))", q)
    if size_match:
        target_size = size_match.group(1).replace(" ", "").upper()
        sized = [
            p for p in results
            if p["name"].upper().startswith(target_size + " ") or p["key"].upper().startswith(target_size + "_")
        ]
        if sized or strict:
            results = sized
        if not results:
            return []

    dur = None
    if any(k in q for k in ["30 day", "30days", "30d", "30", "month", "monthly"]):
        dur = [p for p in results if "30 day" in p["name"].lower()]
    elif any(k in q for k in ["14 day", "14days", "14d", "2 week", "two week"]):
        dur = [p for p in results if "14 day" in p["name"].lower()]
    elif any(k in q for k in ["7 day", "7days", "7d", "week", "weekly"]):
        dur = [p for p in results if "7 day" in p["name"].lower()]
    elif any(k in q for k in ["3 day", "3days", "3d"]):
        dur = [p for p in results if "3 day" in p["name"].lower()]
    elif any(k in q for k in ["2 day", "2days", "2d"]):
        dur = [p for p in results if "2 day" in p["name"].lower()]
    elif any(k in q for k in ["1 day", "1day", "1d", "daily"]):
        dur = [p for p in results if "1 day" in p["name"].lower()]

    if dur is not None:
        if dur or strict:
            results = dur
        if not results:
            return []

    typed = None
    if "awoof" in q:
        typed = [p for p in results if "awoof" in p["name"].lower()]
    elif "sme" in q:
        typed = [p for p in results if "sme" in p["name"].lower()]
    elif "share" in q:
        typed = [p for p in results if "share" in p["name"].lower()]
    elif "social" in q:
        typed = [p for p in results if "social" in p["name"].lower()]
    elif "corp" in q or "cg" in q:
        typed = [p for p in results if "corp" in p["name"].lower() or "cg" in p["key"].lower()]
    elif "gift" in q:
        typed = [p for p in results if "gift" in p["name"].lower()]

    if typed is not None:
        if typed or strict:
            results = typed
        if not results:
            return []

    price_matches = [p for p in results if str(int(p["retail"])) in q.split()]
    if len(price_matches) == 1:
        results = price_matches

    return results


def match_catalog_plan(network: Optional[str], text_query: str) -> List[Dict[str, Any]]:
    all_plans = get_all_catalog_plans(network)
    if not all_plans:
        return []
        
    # 1. Exact Interactive Button Title Match (Meta enforces max 24 chars for list items)
    for p in all_plans:
        net_prefix = f"[{p['network']}] " if not network else ""
        expected_title = f"{net_prefix}{p['name']}"[:24].lower()
        if text_query.lower() == expected_title:
            return [p]
            
    # 2. Strict attribute match
    strict_matches = filter_plans_by_attributes(all_plans, text_query, strict=True)
    if strict_matches:
        return strict_matches
        
    # 3. Fuzzy match
    return filter_plans_by_attributes(all_plans, text_query, strict=False)


def save_user_contact(db: Session, user: User, name_clean: str, norm_phone: str, network: Optional[str] = None) -> SavedContact:
    detected_net = network or detect_network_from_phone(norm_phone) or "MTN"
    existing = (
        db.query(SavedContact)
        .filter(SavedContact.user_id == user.id, SavedContact.nickname == name_clean.lower())
        .first()
    )
    if existing:
        existing.phone_number = norm_phone
        existing.network = detected_net
        existing.display_name = name_clean.title()
        db.commit()
        return existing
    new_contact = SavedContact(
        user_id=user.id,
        nickname=name_clean.lower(),
        display_name=name_clean.title(),
        phone_number=norm_phone,
        network=detected_net
    )
    db.add(new_contact)
    db.commit()
    return new_contact


def stage_pending_order(
    db: Session,
    user: User,
    network: str,
    plan: Dict[str, Any],
    recipient_phone: str,
    recipient_label: Optional[str] = None,
    extra_prefix_note: str = ""
) -> str:
    clear_conv_context(user.phone_number)
    db.query(PendingOrder).filter(PendingOrder.user_id == user.id).delete()

    pending = PendingOrder(
        user_id=user.id,
        network=network.upper(),
        plan_key=plan["key"],
        plan_id=int(plan["plan_id"]),
        plan_name=plan["name"],
        recipient_phone=recipient_phone,
        recipient_label=recipient_label,
        cost_price=float(plan["cost"]),
        retail_price=float(plan["retail"])
    )
    db.add(pending)
    db.commit()

    recip_display = f"{recipient_label} ({recipient_phone})" if recipient_label else recipient_phone

    detected_prefix_net = detect_network_from_phone(recipient_phone)
    prefix_warning = ""
    if (
        detected_prefix_net
        and network.upper() in ("MTN", "AIRTEL", "GLO", "9MOBILE")
        and detected_prefix_net != network.upper()
    ):
        prefix_warning = (
            f"\n⚠️ *Network Prefix Warning:* `{recipient_phone}` is a *{detected_prefix_net}* prefix, "
            f"but you selected *{network.upper()}*! Only confirm if ported.\n"
        )

    balance_warning = ""
    if user.wallet_balance < plan["retail"]:
        balance_warning = (
            f"\n⚠️ *Low Balance:* Your wallet (*₦{user.wallet_balance:,.2f}*) is lower than ₦{plan['retail']:,.0f}. "
            f"Reply *'fund 5000'* to top up first.\n"
        )

    cashback_preview = round(plan["retail"] * 0.015, 2)

    return (
        f"{extra_prefix_note}"
        f"📋 *Confirm Your Swiftwave Pay Order*\n\n"
        f"• *Service:* {network.upper()} — {plan['name']}\n"
        f"• *Recipient:* {recip_display}\n"
        f"• *Price:* ₦{plan['retail']:,.0f}\n"
        f"• *Instant Cashback:* +₦{cashback_preview:,.2f} 🎁\n"
        f"• *Your Wallet:* ₦{user.wallet_balance:,.2f}\n"
        f"{prefix_warning}{balance_warning}\n"
        f"✅ Reply *YES* or *CONFIRM* to complete now, or *CANCEL* to abort."
    )


def format_disambiguation_list(
    sender_phone: str,
    network: Optional[str],
    matching_plans: List[Dict[str, Any]],
    recipient_phone: Optional[str],
    recipient_label: Optional[str],
    header_title: Optional[str] = None,
    pending_save_name: Optional[str] = None,
    page: int = 0
) -> Union[str, Dict[str, Any]]:
    
    set_conv_context(
        sender_phone,
        network=network,
        recipient_phone=recipient_phone,
        recipient_label=recipient_label,
        candidates=matching_plans,
        selected_plan=None,
        pending_save_name=pending_save_name,
        page=page
    )

    # Calculate Pagination 
    has_prev = page > 0
    if len(matching_plans) <= 10:
        show_plans = matching_plans
        has_next = False
    else:
        if not has_prev:
            show_plans = matching_plans[0:9]
            has_next = len(matching_plans) > 9
        else:
            start_idx = 9 + (page - 1) * 8
            remaining = len(matching_plans) - start_idx
            if remaining <= 9:
                show_plans = matching_plans[start_idx : start_idx + remaining]
                has_next = False
            else:
                show_plans = matching_plans[start_idx : start_idx + 8]
                has_next = True

    rows = []
    if has_prev:
        rows.append({"id": "page_prev", "title": "⬅️ Previous", "description": "See previous plans"})
        
    for p in show_plans:
        net_prefix = f"[{p['network']}] " if not network else ""
        title_text = f"{net_prefix}{p['name']}"[:24] # Meta limits Title to 24 chars
        desc_text = f"₦{p['retail']:,.0f}"
        rows.append({"id": p["key"], "title": title_text, "description": desc_text})
        
    if has_next:
        rows.append({"id": "page_next", "title": "Next ➡️", "description": "View more plans"})

    net_label = f" {network}" if network else ""
    list_header = header_title if header_title else f"⚡{net_label} Plans"
    list_header = list_header[:60] # Meta limits Header to 60 chars

    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": list_header},
            "body": {"text": "Select an option from the list below:"},
            "action": {
                "button": "View Plans",
                "sections": [{"title": f"Page {page + 1}", "rows": rows}]
            }
        }
    }


def ask_gemini_assistant(user: User, contacts: List[SavedContact], user_message: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    saved_names = ", ".join([f"{c.display_name} ({c.phone_number})" for c in contacts]) or "None yet"

    system_prompt = f"""
You are Swiftwave Pay, an intelligent, friendly Nigerian WhatsApp VTU & digital services assistant created for Swiftwave Variety Mall (Shop 9 & 10, ABH Plaza, Minna).
Keep your response concise (under 120 words), warm, WhatsApp-formatted (using *bold* and bullet points), and helpful. Understand both English and Nigerian Pidgin naturally.

KEY FACTS YOU MUST FOLLOW:
1. Services available right now (Phase 1):
   - Cheap Data Bundles (MTN, Airtel, Glo).
   - Sachet Voice Minutes (TalkMore): Bypasses borrowed airtime deductions.
   - Direct Airtime Top-up.
   - Instant Exam Result Checker PINs: WAEC (₦3,800), NECO (₦1,350), NABTEB (₦1,200). Saved in user's 'my pins' vault.
   - 1.5% Instant Cashback on every purchase + ₦100 Direct Referral bonus.
2. Note: Utility bills and Cable TV renewals are Phase 2 and NOT active yet. Do not offer them.
3. Customer's current Wallet Balance: ₦{user.wallet_balance:,.2f}. Saved Beneficiaries: {saved_names}.
4. In test/sandbox mode, the user can type 'fund 5000' to add test balance.
5. Never invent prices outside the catalog. Guide the user on exact phrases they can type, such as: 'Send 2GB MTN to Mom', 'Save 08012345678 as Dad', 'Buy WAEC pin', 'Talkmore for me', or 'cmd'.
"""

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300}
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"ℹ️ Gemini conversational fallback skipped: {e}")
    return None


def process_user_message(db: Session, sender_phone: str, message_text: str, profile_name: str = "Boss") -> Union[str, Dict[str, Any]]:
    user = get_or_create_user(db, sender_phone, profile_name)
    text = message_text.strip()
    lower = text.lower()

    # =========================================================================
    # 0. HANDLE PAGINATION CLICKS FIRST
    # =========================================================================
    if lower in {"next ➡️", "next", "next page"}:
        ctx = get_conv_context(sender_phone)
        candidates = ctx.get("candidates", [])
        if candidates:
            new_page = ctx.get("page", 0) + 1
            return format_disambiguation_list(
                sender_phone, ctx.get("network"), candidates, ctx.get("recipient_phone"),
                ctx.get("recipient_label"), page=new_page, pending_save_name=ctx.get("pending_save_name")
            )
        return "⚠️ No active menu to navigate. Type *menu* to start over."

    if lower in {"⬅️ previous", "previous", "prev"}:
        ctx = get_conv_context(sender_phone)
        candidates = ctx.get("candidates", [])
        if candidates:
            new_page = max(0, ctx.get("page", 0) - 1)
            return format_disambiguation_list(
                sender_phone, ctx.get("network"), candidates, ctx.get("recipient_phone"),
                ctx.get("recipient_label"), page=new_page, pending_save_name=ctx.get("pending_save_name")
            )
        return "⚠️ No active menu to navigate. Type *menu* to start over."

    # =========================================================================
    # 0B. DEEP NESTED CLICK ROUTING (Phase 1 Focused)
    # =========================================================================
    if lower == "my wallet balance":
        lower = "balance"
    elif lower == "transaction history":
        lower = "history"
    elif lower == "repeat last order":
        lower = "repeat"
    elif lower == "all commands":
        lower = "cmd"
    elif lower == "swiftwave mall":
        lower = "mall"
        
    # --- Deep Click: Data Networks ---
    if lower in {"buy data", "data"}:
        return {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "🌐 Select Network"},
                "body": {"text": "Which network do you want data for?"},
                "action": {
                    "button": "Choose Network",
                    "sections": [{
                        "title": "Networks",
                        "rows": [
                            {"id": "net_mtn", "title": "MTN Data", "description": "View MTN Data Plans"},
                            {"id": "net_airtel", "title": "Airtel Data", "description": "View Airtel Data Plans"},
                            {"id": "net_glo", "title": "GLO Data", "description": "View GLO Data Plans"},
                            {"id": "net_9mobile", "title": "9Mobile Data", "description": "View 9Mobile Data Plans"}
                        ]
                    }]
                }
            }
        }

    # --- Deep Click: TalkMore Networks ---
    if lower in {"talkmore voice", "talkmore"}:
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "📞 Select a network for TalkMore Voice:"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "tm_mtn", "title": "MTN TalkMore"}},
                        {"type": "reply", "reply": {"id": "tm_airtel", "title": "Airtel TalkMore"}},
                        {"type": "reply", "reply": {"id": "tm_glo", "title": "GLO TalkMore"}}
                    ]
                }
            }
        }

    # --- Deep Click: Exam PINs ---
    if lower == "exam pin":
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "🎓 Which Exam Result PIN do you need?"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "waec_pin", "title": "WAEC PIN"}},
                        {"type": "reply", "reply": {"id": "neco_pin", "title": "NECO PIN"}},
                        {"type": "reply", "reply": {"id": "nabteb_pin", "title": "NABTEB PIN"}}
                    ]
                }
            }
        }

    if lower in {"airtime recharge", "airtime"}:
        return "📱 *Airtime Top-Up*\n\nHow much airtime do you need, and for which number?\n\n👉 _Example: \"Send 500 MTN to Mom\" or \"Buy 1000 airtime for me\"_"

    # =========================================================================
    # 1. CHECK FOR PENDING ORDER CONFIRMATION
    # =========================================================================
    pending = (
        db.query(PendingOrder)
        .filter(PendingOrder.user_id == user.id)
        .order_by(PendingOrder.created_at.desc())
        .first()
    )

    if pending and (datetime.utcnow() - pending.created_at > timedelta(minutes=10)):
        db.delete(pending)
        db.commit()
        pending = None

    if pending:
        if lower in {"yes", "y", "confirm", "send", "proceed", "ok", "okay", "sure"}:
            order_info = {
                "network": pending.network,
                "plan_id": pending.plan_id,
                "plan_name": pending.plan_name,
                "recipient_phone": pending.recipient_phone,
                "cost_price": pending.cost_price,
                "retail_price": pending.retail_price
            }
            db.delete(pending)
            db.commit()

            service = OrderService(db)
            result = service.process_data_order(
                buyer_phone=user.phone_number,
                network=order_info["network"],
                plan_id=order_info["plan_id"],
                recipient_phone=order_info["recipient_phone"],
                cost_price=order_info["cost_price"],
                retail_price=order_info["retail_price"],
                plan_name=order_info["plan_name"]
            )
            return result["message"]

        if lower in {"no", "n", "cancel", "stop", "abort"}:
            db.delete(pending)
            db.commit()
            clear_conv_context(sender_phone)
            return "🚫 Order cancelled. Your wallet was not charged. How else can I help you today?"

    # =========================================================================
    # 2. COMMANDS LIST ('cmd' / 'help') & SWIFTWAVE MALL
    # =========================================================================
    if lower in {"cmd", "commands", "/cmd", "/help"}:
        return (
            "📋 *Swiftwave Pay Commands*\n\n"
            "📦 *data* — Browse & buy data bundles\n"
            "🎉 *awoof* / *talkmore* — Sachet Voice Minutes\n"
            "📱 *airtime* — Instant airtime top-up\n"
            "🎓 *waec* / *neco* — Buy Exam Result Checker PINs\n"
            "🔒 *my pins* — View your purchased PINs\n"
            "💰 *bal* / *balance* — Check wallet & funding account\n"
            "🔗 *ref* / *referral* — Your referral link & rewards\n"
            "📱 *my beneficiaries* — View saved numbers\n"
            "🔁 *repeat* — Repeat your last order in 1 tap\n"
            "📜 *history* — See your last 5 transactions\n"
            "🛍️ *mall* — Shop gadgets at Swiftwave Mall\n\n"
            "💡 *Chat naturally with me! Try typing:*\n"
            "• _'Send 2GB MTN to Mom'_\n"
            "• _'Save 08012345678 as Dad'_\n"
            "• _'Buy WAEC pin'_\n"
            "• _'Talkmore for me'_\n"
            "• _'What Airtel data can 1500 buy?'_"
        )

    if lower == "mall" or any(k in lower for k in ["variety mall", "swiftwave wear", "ecosystem"]):
        return (
            "🛍️ *Swiftwave Variety Mall (Shop 9 & 10, ABH Plaza, Minna)*\n\n"
            "Shop gadgets, phone accessories, ring lights & daily essentials online:\n"
            "👉 https://swiftwave-variety-mall.vercel.app"
        )

    # =========================================================================
    # 3. DEMO WALLET TOP-UP COMMAND
    # =========================================================================
    fund_match = re.search(r"\b(?:fund|topup|top up|credit)\b.*?(\d[\d,]*)", lower)
    if fund_match:
        amount = float(fund_match.group(1).replace(",", ""))
        if 100 <= amount <= 100000:
            user.wallet_balance = round(user.wallet_balance + amount, 2)
            txn = Transaction(
                user_id=user.id,
                amount=amount,
                type="CREDIT",
                description="Instant Wallet Funding",
                reference=f"SW-FUND-{user.id}-{int(time.time())}"
            )
            db.add(txn)
            db.commit()
            return (
                f"💰 *Wallet Funded Successfully!*\n\n"
                f"• *Added:* ₦{amount:,.2f}\n"
                f"• *New Balance:* ₦{user.wallet_balance:,.2f}\n\n"
                f"What would you like to buy today?"
            )

    # =========================================================================
    # 4. WALLET BALANCE & REFERRAL / CASHBACK REWARDS
    # =========================================================================
    if lower in {"bal", "balance", "wallet"} or (
        any(k in lower for k in ["balance", "wallet", "my account", "account number"])
        and not any(k in lower for k in ["buy", "send", "gb", "mb", "what can", "can my"])
    ):
        total_cb = (
            db.query(Transaction)
            .filter(Transaction.user_id == user.id, Transaction.reference.like("SW-CB-%"))
            .all()
        )
        cb_sum = sum(t.amount for t in total_cb)
        return (
            f"💳 *Your Swiftwave Pay Wallet*\n\n"
            f"• *Available Balance:* ₦{user.wallet_balance:,.2f}\n"
            f"• *Total Cashback Earned:* ₦{cb_sum:,.2f} 🎁\n"
            f"• *Dedicated Bank:* {user.bank_name}\n"
            f"• *Account Number:* `{user.account_number}`\n"
            f"• *Account Name:* {user.account_name}\n\n"
            f"💡 _Transfer to your dedicated account above for instant automated funding._"
        )

    if lower in {"ref", "referral", "ref bal"} or "referral" in lower:
        ref_code = user.tracking_reference or f"SW-{user.phone_number[-6:]}"
        total_cb = (
            db.query(Transaction)
            .filter(Transaction.user_id == user.id, Transaction.reference.like("SW-CB-%"))
            .all()
        )
        cb_sum = sum(t.amount for t in total_cb)
        return (
            f"🎁 *Swiftwave Pay Cashback & Referral Program*\n\n"
            f"• *Your Referral Code:* `{ref_code}`\n"
            f"• *Purchase Cashback Rate:* 1.5% Instant Cashback on every order!\n"
            f"• *Total Cashback Earned:* ₦{cb_sum:,.2f}\n"
            f"• *Direct Referral Bonus:* Earn *₦100* when a friend joins with your code `{ref_code}`!"
        )

    # =========================================================================
    # 5. SAVE & VIEW CONTACTS / BENEFICIARIES
    # =========================================================================
    if "save" in lower and re.search(r"\d{10,13}", lower):
        raw_num = re.search(r"\d{10,13}", lower).group(0)
        norm_phone = normalize_ng_phone(raw_num)
        if not norm_phone:
            return "⚠️ Please provide a valid 11-digit Nigerian phone number (e.g., `Save 08031234567 as Mom`)."

        name_part = re.sub(r"\b(save|contact|number|phone|as|for|to|mtn|airtel|glo|9mobile)\b", " ", text, flags=re.IGNORECASE)
        name_part = name_part.replace(raw_num, " ").strip(" -:,.()")
        name_clean = " ".join(name_part.split())

        if not name_clean:
            return "⚠️ What name should I save this number under? Example: *Save 08031234567 as Dad*"

        detected_net = None
        for net in ["MTN", "AIRTEL", "GLO", "9MOBILE"]:
            if net.lower() in lower:
                detected_net = net
                break

        saved = save_user_contact(db, user, name_clean, norm_phone, detected_net)
        return (
            f"✅ *Beneficiary Saved!*\n\n"
            f"• *Name:* {saved.display_name}\n"
            f"• *Number:* {saved.phone_number}\n"
            f"• *Network:* {saved.network}\n\n"
            f"Next time, just say: _'Send 1GB to {saved.display_name}'_!"
        )

    contacts = db.query(SavedContact).filter(SavedContact.user_id == user.id).all()
    if any(k in lower for k in ["my contacts", "saved contacts", "beneficiaries", "my beneficiaries", "contact list", "show contacts"]):
        if not contacts:
            return "📒 You have no saved beneficiaries yet. Reply: *Save 08031234567 as Mom*"
        lines = ["📒 *Your Saved Beneficiaries:*", ""]
        for c in contacts:
            lines.append(f"• *{c.display_name}:* {c.phone_number} ({c.network})")
        return "\n".join(lines)

    # =========================================================================
    # 6. EXAM PIN VAULT ('my pins') & TRANSACTION HISTORY ('history')
    # =========================================================================
    if any(k in lower for k in ["my pins", "my pin", "saved pins", "exam pins", "checker pin"]):
        pin_orders = (
            db.query(Order)
            .filter(Order.user_id == user.id, Order.plan_id.in_(["801", "802", "803"]))
            .order_by(Order.created_at.desc())
            .limit(5)
            .all()
        )
        if not pin_orders:
            return "🎓 You haven't purchased any Exam PINs yet. Reply *'Buy WAEC pin'*!"
        lines = ["🔒 *Your Exam Result Checker PIN Vault:*", ""]
        for o in pin_orders:
            lines.append(f"• *{o.network}:* `{o.external_ref}` _(₦{o.selling_price:,.0f})_")
        return "\n".join(lines)

    if any(k in lower for k in ["history", "my orders", "recent orders", "transactions", "last receipt"]):
        recent_orders = (
            db.query(Order)
            .filter(Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(5)
            .all()
        )
        if not recent_orders:
            return "🧾 You haven't completed any orders yet. Type *cmd* to see everything I can do!"

        lines = ["🧾 *Your Last 5 Orders:*", ""]
        for o in recent_orders:
            plan_info = get_plan_by_id(int(o.plan_id)) if o.plan_id.isdigit() else None
            p_name = plan_info["name"] if plan_info else (f"Airtime ₦{o.selling_price:,.0f}" if o.plan_id == "999" else f"Plan #{o.plan_id}")
            date_str = o.created_at.strftime("%b %d, %H:%M")
            lines.append(
                f"• *{o.network} — {p_name}* → `{o.recipient_phone}`\n"
                f"  ₦{o.selling_price:,.0f} | {o.status} | _{date_str}_"
            )
        lines.append("\n💡 _Reply *'repeat'* anytime to re-order your most recent bundle!_")
        return "\n".join(lines)

    # =========================================================================
    # 7. EXTRACT ENTITIES (CONTACT, UNSAVED NAME, PHONE, "FOR ME", NETWORK)
    # =========================================================================
    ctx = get_conv_context(sender_phone)

    matched_contact: Optional[SavedContact] = None
    for c in contacts:
        if re.search(rf"\b{re.escape(c.nickname)}\b", lower):
            matched_contact = c
            break

    is_self_recharge = any(
        phrase in lower for phrase in ["to me", "for me", "my number", "my line", "myself", "my phone"]
    )

    phone_match = re.search(r"\b(?:\+?234|0)[789][01]\d{8}\b", lower)

    unsaved_contact_name: Optional[str] = None
    if not matched_contact and not phone_match and not is_self_recharge:
        recip_name_match = re.search(
            r"\b(?:to|for|give)\s+([a-zA-Z][a-zA-Z0-9_]{1,18})\s*$",
            text.strip(),
            flags=re.IGNORECASE
        )
        if recip_name_match:
            cand_name = recip_name_match.group(1).strip()
            reserved_words = {
                "me", "myself", "mtn", "airtel", "glo", "9mobile", "data",
                "airtime", "day", "days", "week", "month", "buy", "now"
            }
            if cand_name.lower() not in reserved_words and not re.search(r"\d", cand_name):
                unsaved_contact_name = cand_name.title()

    is_fresh_order_cmd = bool(
        re.match(r"^(?:send|buy|give|i want|abeg send|abeg buy)\b", lower)
        or unsaved_contact_name
        or matched_contact
        or phone_match
    )

    if phone_match:
        recipient_phone = normalize_ng_phone(phone_match.group(0))
        recipient_label = ctx.get("pending_save_name")
    elif matched_contact:
        recipient_phone = matched_contact.phone_number
        recipient_label = matched_contact.display_name
    elif is_self_recharge:
        recipient_phone = normalize_ng_phone(sender_phone) or sender_phone
        recipient_label = "Your Number"
    elif not is_fresh_order_cmd:
        recipient_phone = ctx.get("recipient_phone")
        recipient_label = ctx.get("recipient_label")
    else:
        recipient_phone = None
        recipient_label = None

    explicit_network = None
    for net in ["MTN", "AIRTEL", "GLO", "9MOBILE"]:
        if net.lower() in lower:
            explicit_network = net
            break

    network = explicit_network
    if not network and matched_contact and matched_contact.network:
        network = matched_contact.network
    if not network and phone_match and recipient_phone:
        network = detect_network_from_phone(recipient_phone)
    if not network and is_self_recharge and recipient_phone:
        network = detect_network_from_phone(recipient_phone)
    if not network and not is_fresh_order_cmd:
        network = ctx.get("network")

    # =========================================================================
    # 8. WAEC / NECO / NABTEB RESULT CHECKER PINS
    # =========================================================================
    if any(k in lower for k in ["waec", "neco", "nabteb", "result checker"]):
        for exam_key, exam_details in EXAM_CATALOG.items():
            if exam_key.lower() in lower:
                target_phone = recipient_phone or (normalize_ng_phone(sender_phone) or sender_phone)
                plan_dict = {"key": exam_key, **exam_details}
                return stage_pending_order(db, user, exam_key, plan_dict, target_phone, "Instant WhatsApp PIN Delivery")

        exam_list = [{"key": k, "network": k, **v} for k, v in EXAM_CATALOG.items()]
        return format_disambiguation_list(
            sender_phone=sender_phone,
            network=None,
            matching_plans=exam_list,
            recipient_phone=normalize_ng_phone(sender_phone) or sender_phone,
            recipient_label="Instant WhatsApp Delivery",
            header_title="🎓 Exam PINs"
        )

    # =========================================================================
    # 9. SACHET VOICE MINUTES (TALKMORE) & CALL-TIME CALCULATOR
    # =========================================================================
    mins_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mins|min|minutes|minute)", lower)
    is_talkmore_intent = (
        lower in {"awoof", "talkmore", "minutes", "sachet", "mtn talkmore", "airtel talkmore", "glo talkmore"}
        or any(k in lower for k in ["talkmore", "voice bundle", "call bundle", "xtratime", "owe airtime"])
        or bool(mins_match)
    )

    if is_talkmore_intent and not bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower)) and not any(
        q_word in lower for q_word in ["how does", "explain", "what is", "wetin be", "why"]
    ):
        tm_plans = [{"key": k, "network": network or "MTN", **v} for k, v in TALKMORE_CATALOG.items()]

        if mins_match:
            requested_mins = float(mins_match.group(1))
            suitable = [p for p in tm_plans if p["minutes"] >= requested_mins]
            chosen_tm = suitable[0] if suitable else tm_plans[-1]

            if recipient_phone:
                return stage_pending_order(
                    db=db, user=user, network=network or "MTN", plan=chosen_tm,
                    recipient_phone=recipient_phone, recipient_label=recipient_label
                )
            elif unsaved_contact_name:
                set_conv_context(
                    sender_phone, network=network or "MTN", selected_plan=chosen_tm,
                    candidates=None, pending_save_name=unsaved_contact_name
                )
                return (
                    f"📞 *Call-Time Calculator:* *{chosen_tm['name']}* (*₦{chosen_tm['retail']:,.0f}*).\n\n"
                    f"📒 You haven't saved *{unsaved_contact_name}'s* number yet!\n"
                    f"Reply with *{unsaved_contact_name}'s 11-digit phone number* to stage this order!"
                )
            else:
                set_conv_context(sender_phone, network=network or "MTN", selected_plan=chosen_tm, candidates=None)
                return (
                    f"📞 *Call-Time Calculator:* For *{requested_mins:g} mins* of talk time, your best Sachet Voice Bundle is:\n"
                    f"👉 *{chosen_tm['name']}* — *₦{chosen_tm['retail']:,.0f}*\n"
                    f"_(Bypasses borrowed XtraTime deductions!)_\n\n"
                    f"Which phone number or saved contact should I send it to?"
                )

        # Triggers Interactive List for TalkMore
        return format_disambiguation_list(
            sender_phone=sender_phone, network=network or "MTN", matching_plans=tm_plans,
            recipient_phone=recipient_phone, recipient_label=recipient_label,
            header_title=f"📞 {network or 'MTN'} TalkMore Plans"
        )

    # =========================================================================
    # 10. DIRECT AIRTIME TOP-UP
    # =========================================================================
    if any(k in lower for k in ["airtime", "credit", "recharge card"]) and not any(k in lower for k in ["a2c", "airtime2cash", "sell"]):
        amt_match = re.search(r"(?:₦|naira|n)?\s*(\d{2,5})\b", re.sub(r"\b(?:\+?234|0)[789][01]\d{8}\b", "", lower))
        if amt_match:
            airtime_amt = float(amt_match.group(1))
            if 50 <= airtime_amt <= 50000:
                airtime_plan = {
                    "key": f"AIRTIME_{int(airtime_amt)}", "network": network or "MTN", "plan_id": 999,
                    "name": f"₦{airtime_amt:,.0f} Direct Airtime Top-Up", "cost": round(airtime_amt * 0.97, 2), "retail": airtime_amt
                }
                if recipient_phone:
                    return stage_pending_order(db, user, network or "MTN", airtime_plan, recipient_phone, recipient_label)
                elif unsaved_contact_name:
                    set_conv_context(
                        sender_phone, network=network or "MTN", selected_plan=airtime_plan,
                        candidates=None, pending_save_name=unsaved_contact_name
                    )
                    return (
                        f"📱 Ready to send *₦{airtime_amt:,.0f} Airtime* to *{unsaved_contact_name}*.\n\n"
                        f"📒 Reply with *{unsaved_contact_name}'s 11-digit phone number* to prepare your order!"
                    )
                else:
                    set_conv_context(sender_phone, network=network or "MTN", selected_plan=airtime_plan, candidates=None)
                    return (
                        f"📱 Ready to send *₦{airtime_amt:,.0f} {network or ''} Airtime*.\n"
                        f"Which phone number or saved contact should I recharge?"
                    )
        return (
            "📱 *Instant Airtime Recharge*\n\n"
            "Just tell me the amount and recipient! Examples:\n"
            "• _\"Send 500 airtime to Mom\"_\n"
            "• _\"Buy 1000 MTN airtime for me\"_"
        )

    # =========================================================================
    # 11. REPEAT LAST ORDER
    # =========================================================================
    if any(k in lower for k in ["repeat", "buy again", "last order", "the usual"]):
        last_order = (
            db.query(Order)
            .filter(Order.user_id == user.id, Order.status == "SUCCESS")
            .order_by(Order.created_at.desc())
            .first()
        )
        if not last_order:
            return "⚠️ You don't have a previous successful order to repeat yet."

        plan_info = get_plan_by_id(int(last_order.plan_id)) if last_order.plan_id.isdigit() else None
        if not plan_info:
            return "⚠️ Your previous bundle is no longer in the catalog."

        target_phone = recipient_phone if (phone_match or matched_contact or is_self_recharge) else last_order.recipient_phone
        target_label = recipient_label if (matched_contact or is_self_recharge) else None
        if not target_label:
            for c in contacts:
                if c.phone_number == target_phone:
                    target_label = c.display_name
                    break

        plan_dict = {
            "key": plan_info["plan_key"], "plan_id": plan_info["plan_id"], "name": plan_info["name"],
            "cost": plan_info["cost"], "retail": plan_info["retail"]
        }
        return stage_pending_order(db, user, plan_info["network"], plan_dict, target_phone, target_label)

    # =========================================================================
    # 12. BUDGET DATA SEARCH ("What Airtel data can 1500 buy?")
    # =========================================================================
    is_balance_budget = any(k in lower for k in ["what can my balance", "can my balance buy", "within my balance"])
    clean_for_budget = re.sub(r"\b(?:\+?234|0)[789][01]\d{8}\b", "", lower)

    budget_match = (
        re.search(r"(?:under|below|within|with|for|have|get|can|buy|around|budget|worth|up to)\s*(?:of|for|with|buy)?\s*(?:₦|naira|n)?\s*(\d[\d,]*)", clean_for_budget)
        or re.search(r"(\d[\d,]*)\s*(?:naira|n)?\s*(?:can\s+buy|buy|get|data|bundle|plan)", clean_for_budget)
    )

    budget_limit: Optional[float] = None
    if is_balance_budget:
        budget_limit = max(user.wallet_balance, 0.0)
    elif budget_match and not bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower)):
        raw_val = budget_match.group(1).replace(",", "")
        if 3 <= len(raw_val) <= 5 and int(raw_val) >= 100:
            budget_limit = float(raw_val)

    if budget_limit is not None:
        pool = get_all_catalog_plans(explicit_network or network)
        affordable = [p for p in pool if p["retail"] <= budget_limit]
        affordable.sort(key=lambda x: x["retail"])

        if not affordable:
            return f"⚠️ No data bundles found under *₦{budget_limit:,.0f}*. Our cheapest plans start at *₦150*!"

        target_net = explicit_network or network
        return format_disambiguation_list(
            sender_phone=sender_phone, network=target_net, matching_plans=affordable,
            recipient_phone=recipient_phone, recipient_label=recipient_label,
            header_title=f"💰 Bundles Within ₦{budget_limit:,.0f}"
        )

    # =========================================================================
    # 13. HANDLE FOLLOW-UP REPLIES TO ACTIVE CONTEXT
    # =========================================================================
    if ctx.get("selected_plan") and recipient_phone and not bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower)):
        chosen_plan = ctx["selected_plan"]
        net = chosen_plan.get("network") or detect_network_from_phone(recipient_phone) or ctx.get("network") or "MTN"
        auto_saved_note = ""
        pending_name = ctx.get("pending_save_name")
        if pending_name and phone_match:
            saved_c = save_user_contact(db, user, pending_name, recipient_phone, net)
            recipient_label = saved_c.display_name
            auto_saved_note = f"✅ *Saved {saved_c.display_name} ({recipient_phone}) to your beneficiaries!*\n\n"
        return stage_pending_order(db, user, net, chosen_plan, recipient_phone, recipient_label, extra_prefix_note=auto_saved_note)

    candidates: List[Dict[str, Any]] = ctx.get("candidates") or []
    if candidates and not is_fresh_order_cmd:
        num_choice_match = re.match(r"^(\d{1,2})\b", lower)
        if num_choice_match and not bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower)):
            choice_idx = int(num_choice_match.group(1)) - 1
            if 0 <= choice_idx < len(candidates):
                chosen_plan = candidates[choice_idx]
                net = chosen_plan.get("network") or network or "MTN"
                if recipient_phone:
                    return stage_pending_order(db, user, net, chosen_plan, recipient_phone, recipient_label)
                else:
                    set_conv_context(sender_phone, network=net, selected_plan=chosen_plan, candidates=None)
                    return (
                        f"⚡ Great choice: *{chosen_plan['name']}* (*₦{chosen_plan['retail']:,.0f}*).\n\n"
                        f"Which phone number or saved contact should I send it to?\n"
                        f"_(Reply with a number, a saved name like `Mom`, or `for me`)_"
                    )

        # Meta Button Fallback logic
        narrowed = match_catalog_plan(network, lower)
        if narrowed:
            if len(narrowed) == 1:
                chosen_plan = narrowed[0]
                net = chosen_plan.get("network") or network or "MTN"
                if recipient_phone:
                    return stage_pending_order(db, user, net, chosen_plan, recipient_phone, recipient_label)
                else:
                    set_conv_context(sender_phone, network=net, selected_plan=chosen_plan, candidates=None)
                    return (
                        f"⚡ Great choice: *{chosen_plan['name']}* (*₦{chosen_plan['retail']:,.0f}*).\n\n"
                        f"Which phone number or saved contact should I send it to?"
                    )
            else:
                return format_disambiguation_list(sender_phone, network, narrowed, recipient_phone, recipient_label)

    # =========================================================================
    # 14. RAW NETWORK NAMES & NATURAL LANGUAGE DATA BUYING
    # =========================================================================
    has_data_size = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower))
    has_plan_keyword = any(k in lower for k in ["sme", "awoof", "gifting", "share", "social", "corp"])

    if has_data_size or has_plan_keyword:
        matching_plans = match_catalog_plan(network, lower)
        if not matching_plans and network:
            return f"⚠️ I couldn't find that exact bundle on *{network}*."

        if len(matching_plans) == 1:
            chosen_plan = matching_plans[0]
            resolved_net = chosen_plan.get("network") or network or "MTN"
            if recipient_phone:
                return stage_pending_order(db, user, resolved_net, chosen_plan, recipient_phone, recipient_label)
            elif unsaved_contact_name:
                set_conv_context(
                    sender_phone, network=resolved_net, selected_plan=chosen_plan,
                    candidates=None, pending_save_name=unsaved_contact_name
                )
                return (
                    f"⚡ Got it: *{resolved_net} {chosen_plan['name']}* (*₦{chosen_plan['retail']:,.0f}*).\n\n"
                    f"📒 You haven't saved *{unsaved_contact_name}'s* phone number yet!\n"
                    f"Reply with *{unsaved_contact_name}'s 11-digit number* to prepare your order!"
                )
            else:
                set_conv_context(sender_phone, network=resolved_net, selected_plan=chosen_plan, candidates=None)
                return (
                    f"⚡ *{resolved_net} {chosen_plan['name']}* costs *₦{chosen_plan['retail']:,.0f}*.\n\n"
                    f"Which phone number or saved contact should I send it to?\n"
                    f"_(Reply with `08031234567`, `Mom`, or `for me`)_"
                )
        elif len(matching_plans) > 1:
            return format_disambiguation_list(
                sender_phone, network, matching_plans, recipient_phone, recipient_label,
                pending_save_name=unsaved_contact_name
            )

    is_catalog_request = any(k in lower for k in ["data", "plan", "bundle", "price", "buy", "how much", "list", "show"])
    is_raw_network_click = lower in {"mtn", "airtel", "glo", "9mobile", "mtn data", "airtel data", "glo data", "9mobile data", "net_mtn", "net_airtel", "net_glo", "net_9mobile"}
    
    if network and (is_catalog_request or is_raw_network_click):
        all_net_plans = get_all_catalog_plans(network)
        return format_disambiguation_list(
            sender_phone=sender_phone, network=network, matching_plans=all_net_plans,
            recipient_phone=recipient_phone, recipient_label=recipient_label,
            header_title=f"⚡ {network} Data Plans"
        )

    # =========================================================================
    # 15. MAIN GREETING / HOME MENU 
    # =========================================================================
    if lower in {"hi", "hello", "hey", "salam", "menu", "start", "help", "good morning", "good afternoon", "good evening"}:
        clear_conv_context(sender_phone)
        first_name = user.name.split()[0]
        
        return {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": "⚡ Swiftwave Pay"
                },
                "body": {
                    "text": f"Salam {first_name}! 👋\n\nJoin our WhatsApp Channel for updates:\nhttps://whatsapp.com/channel/0029VbDXBAmLCox8UtDQEb12\n\n💳 *Your Wallet:* ₦{user.wallet_balance:,.2f}\n\nTap the menu button below, or type *cmd* to see all commands!"
                },
                "footer": {
                    "text": "1.5% Instant Cashback on all orders! 🎁"
                },
                "action": {
                    "button": "Main Menu",
                    "sections": [
                        {
                            "title": "📱 Digital Services",
                            "rows": [
                                {"id": "cmd_buy_data", "title": "Buy Data", "description": "MTN, Airtel, GLO, 9Mobile"},
                                {"id": "cmd_airtime", "title": "Airtime Recharge", "description": "Instant Top-up"},
                                {"id": "cmd_talkmore", "title": "TalkMore Voice", "description": "Sachet Voice Minutes"},
                                {"id": "cmd_exam_pin", "title": "Exam PIN", "description": "WAEC, NECO, NABTEB"}
                            ]
                        },
                        {
                            "title": "⚙️ Account & Tools",
                            "rows": [
                                {"id": "cmd_balance", "title": "My Wallet Balance", "description": "Check balance & fund"},
                                {"id": "cmd_repeat", "title": "Repeat Last Order", "description": "Buy again instantly"},
                                {"id": "cmd_history", "title": "Transaction History", "description": "See recent orders"}
                            ]
                        },
                        {
                            "title": "🌐 Explore More",
                            "rows": [
                                {"id": "cmd_mall", "title": "Swiftwave Mall", "description": "Shop gadgets & accessories"},
                                {"id": "cmd_help", "title": "All Commands", "description": "View typing instructions"}
                            ]
                        }
                    ]
                }
            }
        }

    # =========================================================================
    # 16. GEMINI AI CONVERSATIONAL FALLBACK
    # =========================================================================
    ai_reply = ask_gemini_assistant(user, contacts, text)
    if ai_reply:
        return ai_reply

    return (
        "🤖 *Swiftwave Pay*\n\n"
        "💡 *Chat naturally with me! Try typing:*\n"
        "• _'Send 2GB MTN to Mom'_\n"
        "• _'Save 08012345678 as Dad'_\n"
        "• _'Buy WAEC pin'_\n"
        "• _'Talkmore for me'_\n"
        "• _'What Airtel data can 1500 buy?'_"
    )