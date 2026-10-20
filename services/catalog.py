"""
Swiftwave Complete Phase 1 Catalog:
1. DATA_CATALOG (MTN, AIRTEL, GLO, 9MOBILE)
2. TALKMORE_CATALOG (Sachet Voice Minutes - Bypasses Borrowed Airtime Debt)
3. EXAM_CATALOG (WAEC, NECO, NABTEB Result Checker PINs)
"""

DATA_CATALOG = {
    "MTN": {
        "110MB_1D": {"plan_id": 43, "cost": 99.0, "retail": 150.0, "name": "110MB Gifting (1 Day)", "validity": "1 Day"},
        "230MB_1D": {"plan_id": 74, "cost": 200.0, "retail": 300.0, "name": "230MB Gifting (1 Day)", "validity": "1 Day"},
        "500MB_SME_2D": {"plan_id": 76, "cost": 250.0, "retail": 350.0, "name": "500MB SME (2 Days)", "validity": "2 Days"},
        "500MB_SHARE_30D": {"plan_id": 44, "cost": 300.0, "retail": 450.0, "name": "500MB Data Share (30 Days)", "validity": "30 Days"},
        "1GB_SME_2D": {"plan_id": 77, "cost": 399.0, "retail": 550.0, "name": "1GB SME (2 Days)", "validity": "2 Days"},
        "1GB_AWOOF_30D": {"plan_id": 78, "cost": 430.0, "retail": 600.0, "name": "1GB Awoof (30 Days)", "validity": "30 Days"},
        "1GB_SME_7D": {"plan_id": 45, "cost": 450.0, "retail": 650.0, "name": "1GB SME (7 Days)", "validity": "7 Days"},
        "1GB_SME_30D": {"plan_id": 46, "cost": 570.0, "retail": 800.0, "name": "1GB SME (30 Days)", "validity": "30 Days"},
        "2GB_GIFT_7D": {"plan_id": 71, "cost": 900.0, "retail": 1200.0, "name": "2GB Gifting (7 Days)", "validity": "7 Days"},
        "2GB_SME_7D": {"plan_id": 47, "cost": 930.0, "retail": 1250.0, "name": "2GB SME (7 Days)", "validity": "7 Days"},
        "2GB_SME_30D": {"plan_id": 48, "cost": 1150.0, "retail": 1500.0, "name": "2GB SME (30 Days)", "validity": "30 Days"},
        "3GB_SME_30D": {"plan_id": 49, "cost": 1370.0, "retail": 1800.0, "name": "3GB SME (30 Days)", "validity": "30 Days"},
        "4GB_GIFT_2D": {"plan_id": 61, "cost": 1175.0, "retail": 1550.0, "name": "4GB Gifting (2 Days)", "validity": "2 Days"},
        "5GB_SME_30D": {"plan_id": 50, "cost": 2050.0, "retail": 2600.0, "name": "5GB SME (30 Days)", "validity": "30 Days"},
        "6GB_GIFT_7D": {"plan_id": 53, "cost": 2495.0, "retail": 3100.0, "name": "6GB Gifting (7 Days)", "validity": "7 Days"},
        "10GB_GIFT_30D": {"plan_id": 67, "cost": 4800.0, "retail": 5600.0, "name": "10GB Gifting (30 Days)", "validity": "30 Days"},
        "36GB_GIFT_30D": {"plan_id": 57, "cost": 10900.0, "retail": 12500.0, "name": "36GB Gifting (30 Days)", "validity": "30 Days"},
        "75GB_SME_30D": {"plan_id": 51, "cost": 17990.0, "retail": 20000.0, "name": "75GB SME (30 Days)", "validity": "30 Days"}
    },
    "AIRTEL": {
        "1GB_SOC_3D": {"plan_id": 70, "cost": 295.0, "retail": 400.0, "name": "1GB Social (3 Days)", "validity": "3 Days"},
        "500MB_GIFT_7D": {"plan_id": 13, "cost": 490.0, "retail": 650.0, "name": "500MB Gifting (7 Days)", "validity": "7 Days"},
        "1.5GB_GIFT_1D": {"plan_id": 69, "cost": 500.0, "retail": 700.0, "name": "1.5GB Gifting (1 Day)", "validity": "1 Day"},
        "1.5GB_GIFT_2D": {"plan_id": 66, "cost": 599.0, "retail": 800.0, "name": "1.5GB Gifting (2 Days)", "validity": "2 Days"},
        "1GB_GIFT_7D": {"plan_id": 15, "cost": 800.0, "retail": 1050.0, "name": "1GB Gifting (7 Days)", "validity": "7 Days"},
        "2GB_GIFT_30D": {"plan_id": 17, "cost": 1490.0, "retail": 1850.0, "name": "2GB Gifting (30 Days)", "validity": "30 Days"},
        "5GB_GIFT_7D": {"plan_id": 52, "cost": 1570.0, "retail": 1950.0, "name": "5GB Gifting (7 Days)", "validity": "7 Days"},
        "3GB_GIFT_30D": {"plan_id": 18, "cost": 1960.0, "retail": 2400.0, "name": "3GB Gifting (30 Days)", "validity": "30 Days"},
        "6GB_SME_7D": {"plan_id": 22, "cost": 2455.0, "retail": 2950.0, "name": "6GB SME (7 Days)", "validity": "7 Days"},
        "4GB_GIFT_30D": {"plan_id": 19, "cost": 2570.0, "retail": 3100.0, "name": "4GB Gifting (30 Days)", "validity": "30 Days"},
        "8GB_GIFT_30D": {"plan_id": 20, "cost": 2999.0, "retail": 3600.0, "name": "8GB Gifting (30 Days)", "validity": "30 Days"},
        "10GB_GIFT_30D": {"plan_id": 21, "cost": 4070.0, "retail": 4800.0, "name": "10GB Gifting (30 Days)", "validity": "30 Days"}
    },
    "GLO": {
        "200MB_CG_1D": {"plan_id": 42, "cost": 92.0, "retail": 150.0, "name": "200MB Corp Gifting (1 Day)", "validity": "1 Day"},
        "500MB_CG_30D": {"plan_id": 35, "cost": 225.0, "retail": 350.0, "name": "500MB Corp Gifting (30 Days)", "validity": "30 Days"},
        "1GB_AWOOF_1D": {"plan_id": 84, "cost": 250.0, "retail": 350.0, "name": "1GB Awoof (1 Day)", "validity": "1 Day"},
        "1GB_CG_3D": {"plan_id": 68, "cost": 300.0, "retail": 450.0, "name": "1GB Corp Gifting (3 Days)", "validity": "3 Days"},
        "1GB_CG_30D": {"plan_id": 36, "cost": 425.0, "retail": 600.0, "name": "1GB Corp Gifting (30 Days)", "validity": "30 Days"},
        "1GB_GIFT_14D": {"plan_id": 41, "cost": 485.0, "retail": 650.0, "name": "1GB Gifting (14 Days)", "validity": "14 Days"},
        "2GB_CG_30D": {"plan_id": 40, "cost": 850.0, "retail": 1150.0, "name": "2GB Corp Gifting (30 Days)", "validity": "30 Days"},
        "3GB_CG_30D": {"plan_id": 37, "cost": 1300.0, "retail": 1650.0, "name": "3GB Corp Gifting (30 Days)", "validity": "30 Days"},
        "5GB_CG_7D": {"plan_id": 54, "cost": 1699.0, "retail": 2100.0, "name": "5GB Corp Gifting (7 Days)", "validity": "7 Days"},
        "5GB_CG_30D": {"plan_id": 38, "cost": 2250.0, "retail": 2750.0, "name": "5GB Corp Gifting (30 Days)", "validity": "30 Days"},
        "10GB_CG_30D": {"plan_id": 39, "cost": 4390.0, "retail": 5200.0, "name": "10GB Corp Gifting (30 Days)", "validity": "30 Days"},
        "20.5GB_GIFT_30D": {"plan_id": 59, "cost": 5300.0, "retail": 6200.0, "name": "20.5GB Gifting (30 Days)", "validity": "30 Days"},
        "107GB_GIFT_30D": {"plan_id": 58, "cost": 19300.0, "retail": 21500.0, "name": "107GB Gifting (30 Days)", "validity": "30 Days"}
    },
    "9MOBILE": {}
}

# --- SACHET VOICE MINUTES (TALKMORE / AWOOF CALL BUNDLES) ---
# Key selling point: Direct TalkMore bundles DO NOT get deducted if user owes XtraTime!
TALKMORE_CATALOG = {
    "TALKMORE_8.5M": {
        "plan_id": 901,
        "minutes": 8.5,
        "cost": 98.0,
        "retail": 110.0,
        "name": "8.5 Mins TalkMore Sachet (₦500 Talk Value)",
        "validity": "3 Days"
    },
    "TALKMORE_21M": {
        "plan_id": 902,
        "minutes": 21.0,
        "cost": 195.0,
        "retail": 220.0,
        "name": "21 Mins TalkMore Sachet (₦1,000 Talk Value)",
        "validity": "7 Days"
    },
    "TALKMORE_55M": {
        "plan_id": 903,
        "minutes": 55.0,
        "cost": 490.0,
        "retail": 550.0,
        "name": "55 Mins TalkMore Sachet (₦2,500 Talk Value)",
        "validity": "14 Days"
    },
    "TALKMORE_110M": {
        "plan_id": 904,
        "minutes": 110.0,
        "cost": 960.0,
        "retail": 1050.0,
        "name": "110 Mins TalkMore Mega (₦5,000 Talk Value)",
        "validity": "30 Days"
    }
}

# --- EXAM RESULT CHECKER PINS (PHASE 1) ---
EXAM_CATALOG = {
    "WAEC": {
        "plan_id": 801,
        "cost": 3450.0,
        "retail": 3800.0,
        "name": "WAEC Result Checker PIN (Instant Token)"
    },
    "NECO": {
        "plan_id": 802,
        "cost": 1100.0,
        "retail": 1350.0,
        "name": "NECO Result Checker Token"
    },
    "NABTEB": {
        "plan_id": 803,
        "cost": 950.0,
        "retail": 1200.0,
        "name": "NABTEB Result Checker PIN"
    }
}


def get_network_plans(network: str):
    """Returns all plans available for a given telco network."""
    return DATA_CATALOG.get(network.upper(), {})


def get_plan_by_id(plan_id: int):
    """Reverse lookup across Data, TalkMore, and Exam catalogs."""
    pid = int(plan_id)
    for net, plans in DATA_CATALOG.items():
        for key, details in plans.items():
            if details["plan_id"] == pid:
                return {"network": net, "plan_key": key, **details}
    for key, details in TALKMORE_CATALOG.items():
        if details["plan_id"] == pid:
            return {"network": "TALKMORE", "plan_key": key, **details}
    for key, details in EXAM_CATALOG.items():
        if details["plan_id"] == pid:
            return {"network": key, "plan_key": key, **details}
    return None


def format_menu_text(network: str) -> str:
    """Generates clean WhatsApp-friendly menu text for customers."""
    plans = get_network_plans(network)
    if not plans:
        return f"⚠️ {network.upper()} plans are temporarily undergoing provider maintenance."

    lines = [f"*⚡ SWIFTWAVE {network.upper()} DATA BUNDLES ⚡*", ""]
    for idx, (key, details) in enumerate(plans.items(), start=1):
        lines.append(f"*{idx}.* {details['name']} — *₦{details['retail']:,.0f}*")
    lines.append("\n_Reply with the option number or type your choice naturally._")
    return "\n".join(lines)


def format_talkmore_menu() -> str:
    """Generates the Sachet Voice Minutes (TalkMore) menu with the XtraTime hook."""
    lines = [
        "🎉 *SWIFTWAVE SACHET VOICE MINUTES (TALKMORE)* 📞",
        "_💡 Owe borrowed airtime (XtraTime)? TalkMore bundles bypass debt deductions and give 4x more talk time!_",
        ""
    ]
    for idx, (key, details) in enumerate(TALKMORE_CATALOG.items(), start=1):
        lines.append(f"*{idx}.* {details['name']} — *₦{details['retail']:,.0f}* ({details['validity']})")
    lines.append(
        "\n_Reply with *1 - 4*, or tell me how many minutes you want to talk (e.g., 'I want 30 mins call for Mom')!_"
    )
    return "\n".join(lines)