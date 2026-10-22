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
        
    for p in all_plans:
        net_prefix = f"[{p['network']}] " if not network else ""
        expected_title = f"{net_prefix}{p['name']}"[:24].lower()
        if text_query.lower() == expected_title:
            return [p]
            
    strict_matches = filter_plans_by_attributes(all_plans, text_query, strict=True)
    if strict_matches:
        return strict_matches
        
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
        prefix_warning = f"\n⚠️ *Note:* `{recipient_phone}` is a *{detected_prefix_net}* number.\n"

    balance_warning = ""
    if user.wallet_balance < plan["retail"]:
        balance_warning = f"\n⚠️ Wallet too low. Reply *fund 5000* to top up.\n"

    cashback_preview = round(plan["retail"] * 0.015, 2)

    return (
        f"{extra_prefix_note}"
        f"🛒 *Confirm Order*\n"
        f"📱 {network.upper()} {plan['name']} ➔ {recip_display}\n"
        f"💰 ₦{plan['retail']:,.0f} (Cashback: +₦{cashback_preview:,.2f})\n"
        f"💳 Wallet: ₦{user.wallet_balance:,.2f}\n"
        f"{prefix_warning}{balance_warning}\n"
        f"✅ Reply *YES* or *CANCEL*"
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
        title_text = f"{net_prefix}{p['name']}"[:24]
        desc_text = f"₦{p['retail']:,.0f}"
        rows.append({"id": p["key"], "title": title_text, "description": desc_text})
        
    if has_next:
        rows.append({"id": "page_next", "title": "Next ➡️", "description": "View more plans"})

    net_label = f" {network}" if network else ""
    list_header = header_title if header_title else f"⚡{net_label} Plans"
    list_header = list_header[:60]

    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": list_header},
            "body": {"text": "Select an option below:"},
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
You are Swiftwave Pay. Be extremely minimal and direct. NO LONG PARAGRAPHS. Keep responses under 30 words.
1. Phase 1 Services: Cheap Data, TalkMore Voice Minutes, Airtime, WAEC/NECO PINs.
2. Utility bills and Cable TV are Phase 2. Do not offer them.
3. Wallet: ₦{user.wallet_balance:,.2f}. Contacts: {saved_names}.
4. Guide users briefly if they need help (e.g. 'Type cmd' or 'Send 2GB MTN to Mom').
"""

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 100}
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"ℹ️ Gemini conversational fallback skipped: {e}")
    return None


def process_user_message(db: Session, sender_phone: str, message_text: str, profile_name: str = "Boss") -> Union[str, Dict[str, Any], List[Dict[str, Any]]]:
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
        return "⚠️ No active menu. Type *menu*."

    if lower in {"⬅️ previous", "previous", "prev"}:
        ctx = get_conv_context(sender_phone)
        candidates = ctx.get("candidates", [])
        if candidates:
            new_page = max(0, ctx.get("page", 0) - 1)
            return format_disambiguation_list(
                sender_phone, ctx.get("network"), candidates, ctx.get("recipient_phone"),
                ctx.get("recipient_label"), page=new_page, pending_save_name=ctx.get("pending_save_name")
            )
        return "⚠️ No active menu. Type *menu*."

    # =========================================================================
    # 0B. DEEP NESTED CLICK ROUTING (Phase 1 Focused)
    # =========================================================================
    if lower == "my wallet balance":
        lower = "balance"
    elif lower == "transaction history":
        lower = "history"
    elif lower == "repeat last order":
        lower = "repeat"
    elif lower in {"all commands", "cmd_more_cmds", "help / commands"}:
        lower = "cmd"
    elif lower in {"swiftwave mall", "cmd_mall"}:
        lower = "mall"
        
    if lower in {"buy data", "data", "cmd_buy_data"}:
        return {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "🌐 Select Network"},
                "body": {"text": "Choose your network:"},
                "action": {
                    "button": "Networks",
                    "sections": [{
                        "title": "Networks",
                        "rows": [
                            {"id": "net_mtn", "title": "MTN Data"},
                            {"id": "net_airtel", "title": "Airtel Data"},
                            {"id": "net_glo", "title": "GLO Data"},
                            {"id": "net_9mobile", "title": "9Mobile Data"}
                        ]
                    }]
                }
            }
        }

    if lower in {"talkmore voice", "talkmore", "cmd_talkmore"}:
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Select a network for TalkMore:"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "tm_airtel", "title": "AIRTEL TalkMore"}},
                        {"type": "reply", "reply": {"id": "tm_glo", "title": "Glo TalkMore"}},
                        {"type": "reply", "reply": {"id": "tm_mtn", "title": "MTN TalkMore"}}
                    ]
                }
            }
        }

    if lower in {"exam pin", "cmd_exam_pin"}:
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "🎓 Select Exam:"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "waec_pin", "title": "WAEC"}},
                        {"type": "reply", "reply": {"id": "neco_pin", "title": "NECO"}},
                        {"type": "reply", "reply": {"id": "nabteb_pin", "title": "NABTEB"}}
                    ]
                }
            }
        }

    if lower in {"airtime recharge", "airtime", "cmd_airtime"}:
        return "📱 *Airtime*\nHow much and for which number?\n_Example: Send 500 to Mom_"

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
            return "🚫 Cancelled."

    # =========================================================================
    # 2. COMMANDS LIST ('cmd' / 'help') & SWIFTWAVE MALL
    # =========================================================================
    if lower in {"cmd", "commands", "/cmd", "/help"}:
        return (
            "📋 *Commands*\n"
            "📦 *data* — Buy data\n"
            "🎉 *talkmore* — Voice Minutes\n"
            "📱 *airtime* — Buy airtime\n"
            "🎓 *waec* / *neco* — Exam PINs\n"
            "💰 *bal* — Check wallet\n"
            "🔁 *repeat* — Repeat last order\n"
            "🛍️ *mall* — Shop online\n\n"
            "💡 *Try typing:*\n"
            "• _'Send 2GB MTN to Mom'_\n"
            "• _'Save 08012345678 as Dad'_"
        )

    if lower == "mall" or any(k in lower for k in ["variety mall", "swiftwave wear", "ecosystem"]):
        return (
            "🛍️ *Swiftwave Variety Mall*\n"
            "Shop gadgets & accessories:\n"
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
            return f"💰 *Wallet Funded!*\n➕ Added: ₦{amount:,.2f}\n💳 Balance: ₦{user.wallet_balance:,.2f}\n\nWhat would you like to buy?"

    # =========================================================================
    # 4. WALLET BALANCE & REFERRAL / CASHBACK REWARDS
    # =========================================================================
    if lower in {"bal", "balance", "wallet"} or (
        any(k in lower for k in ["balance", "wallet", "my account", "account number"])
        and not any(k in lower for k in ["buy", "send", "gb", "mb", "what can", "can my"])
    ):
        return (
            f"💳 *Your Wallet*\n"
            f"Balance: ₦{user.wallet_balance:,.2f}\n\n"
            f"🏦 *Funding Account:*\n"
            f"Bank: {user.bank_name}\n"
            f"Acc: `{user.account_number}`\n"
            f"Name: {user.account_name}"
        )

    if lower in {"ref", "referral", "ref bal"} or "referral" in lower:
        ref_code = user.tracking_reference or f"SW-{user.phone_number[-6:]}"
        return f"🎁 *Cashback & Referrals*\nYour Code: `{ref_code}`\nEarn 1.5% cashback on orders + ₦100 per referral!"

    # =========================================================================
    # 5. SAVE & VIEW CONTACTS / BENEFICIARIES
    # =========================================================================
    if "save" in lower and re.search(r"\d{10,13}", lower):
        raw_num = re.search(r"\d{10,13}", lower).group(0)
        norm_phone = normalize_ng_phone(raw_num)
        if not norm_phone:
            return "⚠️ Invalid number. Example: `Save 08031234567 as Mom`."

        name_part = re.sub(r"\b(save|contact|number|phone|as|for|to|mtn|airtel|glo|9mobile)\b", " ", text, flags=re.IGNORECASE)
        name_part = name_part.replace(raw_num, " ").strip(" -:,.()")
        name_clean = " ".join(name_part.split())

        if not name_clean:
            return "⚠️ Name missing. Example: *Save 08031234567 as Mom*"

        detected_net = None
        for net in ["MTN", "AIRTEL", "GLO", "9MOBILE"]:
            if net.lower() in lower:
                detected_net = net
                break

        saved = save_user_contact(db, user, name_clean, norm_phone, detected_net)
        return f"✅ *Saved {saved.display_name}* ({saved.phone_number})\nNext time, type: _Send 1GB to {saved.display_name}_"

    contacts = db.query(SavedContact).filter(SavedContact.user_id == user.id).all()
    if any(k in lower for k in ["my contacts", "saved contacts", "beneficiaries", "my beneficiaries", "contact list", "show contacts"]):
        if not contacts:
            return "📒 No saved numbers. Reply: *Save 08031234567 as Mom*"
        lines = ["📒 *Saved Numbers:*"]
        for c in contacts:
            lines.append(f"• {c.display_name}: {c.phone_number}")
        return "\n".join(lines)

    # =========================================================================
    # 6. EXAM PIN VAULT & HISTORY
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
            return "🎓 No PINs purchased yet."
        lines = ["🔒 *Your Exam PINs:*"]
        for o in pin_orders:
            lines.append(f"• {o.network}: `{o.external_ref}`")
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
            return "🧾 No recent orders. Type *cmd* to start."

        lines = ["🧾 *Last 5 Orders:*"]
        for o in recent_orders:
            plan_info = get_plan_by_id(int(o.plan_id)) if o.plan_id.isdigit() else None
            p_name = plan_info["name"] if plan_info else (f"Airtime ₦{o.selling_price:,.0f}" if o.plan_id == "999" else f"Plan #{o.plan_id}")
            lines.append(f"• {o.network} {p_name} ➔ {o.recipient_phone} ({o.status})")
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
            reserved_words = {"me", "myself", "mtn", "airtel", "glo", "9mobile", "data", "airtime", "buy", "now"}
            if cand_name.lower() not in reserved_words and not re.search(r"\d", cand_name):
                unsaved_contact_name = cand_name.title()

    is_fresh_order_cmd = bool(
        re.match(r"^(?:send|buy|give|i want)\b", lower)
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
                return stage_pending_order(db, user, exam_key, plan_dict, target_phone, "WhatsApp PIN Delivery")

        exam_list = [{"key": k, "network": k, **v} for k, v in EXAM_CATALOG.items()]
        return format_disambiguation_list(
            sender_phone=sender_phone, network=None, matching_plans=exam_list,
            recipient_phone=normalize_ng_phone(sender_phone) or sender_phone,
            recipient_label="WhatsApp Delivery", header_title="🎓 Exam PINs"
        )

    # =========================================================================
    # 9. SACHET VOICE MINUTES (TALKMORE)
    # =========================================================================
    mins_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mins|min|minutes|minute)", lower)
    is_talkmore_intent = (
        lower in {"awoof", "talkmore", "minutes", "sachet", "mtn talkmore", "airtel talkmore", "glo talkmore"}
        or any(k in lower for k in ["talkmore", "voice bundle", "call bundle"])
        or bool(mins_match)
    )

    if is_talkmore_intent and not bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower)):
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
                return f"⚡ {chosen_tm['name']}\nReply with *{unsaved_contact_name}'s 11-digit phone number*."
            else:
                set_conv_context(sender_phone, network=network or "MTN", selected_plan=chosen_tm, candidates=None)
                return f"⚡ {chosen_tm['name']}\nWhich phone number should I send it to?"

        return format_disambiguation_list(
            sender_phone=sender_phone, network=network or "MTN", matching_plans=tm_plans,
            recipient_phone=recipient_phone, recipient_label=recipient_label,
            header_title=f"📞 {network or 'MTN'} TalkMore"
        )

    # =========================================================================
    # 10. DIRECT AIRTIME TOP-UP
    # =========================================================================
    if any(k in lower for k in ["airtime", "credit", "recharge card"]):
        amt_match = re.search(r"(?:₦|naira|n)?\s*(\d{2,5})\b", re.sub(r"\b(?:\+?234|0)[789][01]\d{8}\b", "", lower))
        if amt_match:
            airtime_amt = float(amt_match.group(1))
            if 50 <= airtime_amt <= 50000:
                airtime_plan = {
                    "key": f"AIRTIME_{int(airtime_amt)}", "network": network or "MTN", "plan_id": 999,
                    "name": f"₦{airtime_amt:,.0f} Airtime", "cost": round(airtime_amt * 0.97, 2), "retail": airtime_amt
                }
                if recipient_phone:
                    return stage_pending_order(db, user, network or "MTN", airtime_plan, recipient_phone, recipient_label)
                elif unsaved_contact_name:
                    set_conv_context(
                        sender_phone, network=network or "MTN", selected_plan=airtime_plan,
                        candidates=None, pending_save_name=unsaved_contact_name
                    )
                    return f"📱 Ready to send ₦{airtime_amt:,.0f} Airtime.\nReply with *{unsaved_contact_name}'s 11-digit number*."
                else:
                    set_conv_context(sender_phone, network=network or "MTN", selected_plan=airtime_plan, candidates=None)
                    return f"📱 Ready to send ₦{airtime_amt:,.0f} Airtime.\nWhich phone number should I recharge?"
        return "📱 *Airtime*\nHow much and to which number?\n_Example: Send 500 to Mom_"

    # =========================================================================
    # 11. REPEAT LAST ORDER
    # =========================================================================
    if any(k in lower for k in ["repeat", "buy again", "last order"]):
        last_order = (
            db.query(Order)
            .filter(Order.user_id == user.id, Order.status == "SUCCESS")
            .order_by(Order.created_at.desc())
            .first()
        )
        if not last_order:
            return "⚠️ No previous successful order found."

        plan_info = get_plan_by_id(int(last_order.plan_id)) if last_order.plan_id.isdigit() else None
        if not plan_info:
            return "⚠️ Plan no longer available."

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
    # 12. BUDGET DATA SEARCH
    # =========================================================================
    is_balance_budget = any(k in lower for k in ["what can my balance", "can my balance buy"])
    clean_for_budget = re.sub(r"\b(?:\+?234|0)[789][01]\d{8}\b", "", lower)

    budget_match = (
        re.search(r"(?:under|below|within|for)\s*(?:₦|naira|n)?\s*(\d[\d,]*)", clean_for_budget)
        or re.search(r"(\d[\d,]*)\s*(?:naira|n)?\s*(?:can\s+buy|buy|data)", clean_for_budget)
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
            return f"⚠️ No bundles under ₦{budget_limit:,.0f}."

        target_net = explicit_network or network
        return format_disambiguation_list(
            sender_phone=sender_phone, network=target_net, matching_plans=affordable,
            recipient_phone=recipient_phone, recipient_label=recipient_label,
            header_title=f"💰 Bundles Under ₦{budget_limit:,.0f}"
        )

    # =========================================================================
    # 13. HANDLE FOLLOW-UP REPLIES
    # =========================================================================
    if ctx.get("selected_plan") and recipient_phone and not bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower)):
        chosen_plan = ctx["selected_plan"]
        net = chosen_plan.get("network") or detect_network_from_phone(recipient_phone) or ctx.get("network") or "MTN"
        auto_saved_note = ""
        pending_name = ctx.get("pending_save_name")
        if pending_name and phone_match:
            saved_c = save_user_contact(db, user, pending_name, recipient_phone, net)
            recipient_label = saved_c.display_name
            auto_saved_note = f"✅ *Saved {saved_c.display_name}*\n"
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
                    return f"⚡ {chosen_plan['name']}\nWhich phone number?"

        narrowed = match_catalog_plan(network, lower)
        if narrowed:
            if len(narrowed) == 1:
                chosen_plan = narrowed[0]
                net = chosen_plan.get("network") or network or "MTN"
                if recipient_phone:
                    return stage_pending_order(db, user, net, chosen_plan, recipient_phone, recipient_label)
                else:
                    set_conv_context(sender_phone, network=net, selected_plan=chosen_plan, candidates=None)
                    return f"⚡ {chosen_plan['name']}\nWhich phone number?"
            else:
                return format_disambiguation_list(sender_phone, network, narrowed, recipient_phone, recipient_label)

    # =========================================================================
    # 14. RAW NETWORK NAMES & NATURAL LANGUAGE DATA
    # =========================================================================
    has_data_size = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:gb|mb)\b", lower))
    has_plan_keyword = any(k in lower for k in ["sme", "awoof", "gifting", "share", "social", "corp"])

    if has_data_size or has_plan_keyword:
        matching_plans = match_catalog_plan(network, lower)
        if not matching_plans and network:
            return f"⚠️ Plan not found."

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
                return f"⚡ {chosen_plan['name']}\nReply with *{unsaved_contact_name}'s 11-digit number*."
            else:
                set_conv_context(sender_phone, network=resolved_net, selected_plan=chosen_plan, candidates=None)
                return f"⚡ {chosen_plan['name']}\nWhich phone number should I send it to?"
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
            header_title=f"⚡ {network} Data"
        )

    # =========================================================================
    # 15. MAIN GREETING / HOME MENU (DUAL INLINE BUTTON MESSAGES)
    # =========================================================================
    if lower in {"hi", "hello", "hey", "salam", "menu", "start", "help", "good morning", "good afternoon", "good evening"}:
        clear_conv_context(sender_phone)
        first_name = user.name.split()[0]
        
        # We return a List of two interactive messages to bypass the 3-button limit
        return [
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": f"Hi {first_name}! 👋\n\nWelcome to Swiftwave - Smart Pay! 🤖\nJust tell me what you need! Meanwhile, join our WhatsApp Channel for update.\nhttps://whatsapp.com/channel/0029VbDXBAmLCox8UtDQEb12"
                    },
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": "cmd_buy_data", "title": "Buy Data"}},
                            {"type": "reply", "reply": {"id": "cmd_airtime", "title": "Airtime"}},
                            {"type": "reply", "reply": {"id": "cmd_talkmore", "title": "TalkMore"}}
                        ]
                    }
                }
            },
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": "More options..."
                    },
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": "cmd_exam_pin", "title": "Exam PIN"}},
                            {"type": "reply", "reply": {"id": "cmd_mall", "title": "Swiftwave Mall"}},
                            {"type": "reply", "reply": {"id": "cmd_more_cmds", "title": "Help / Commands"}}
                        ]
                    }
                }
            }
        ]

    # =========================================================================
    # 16. GEMINI AI CONVERSATIONAL FALLBACK
    # =========================================================================
    ai_reply = ask_gemini_assistant(user, contacts, text)
    if ai_reply:
        return ai_reply

    return "🤖 Try typing: _'Send 2GB MTN to Mom'_ or _'cmd'_."