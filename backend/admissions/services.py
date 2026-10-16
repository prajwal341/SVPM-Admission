from decimal import Decimal, InvalidOperation

LATEST_FEE_YEAR = "2025-26"
RATES = {"OPEN": Decimal("89350"), "SC": Decimal("350"), "CONCESSION": Decimal("10867"), "OBC_EBC_EWS": Decimal("50109")}

def calculate_latest_fee(category, gender, has_ebc_ews_certificate=False, carried_balance=0):
    category, gender = category.strip().upper(), gender.strip().upper()
    try:
        balance = Decimal(str(carried_balance))
    except InvalidOperation as exc:
        raise ValueError("Invalid balance") from exc
    if balance < 0:
        raise ValueError("Balance cannot be negative")
    if category == "SC":
        group, amount, reason = "SC", RATES["SC"], "₹350 category"
    elif gender in {"F", "FEMALE"}:
        group, amount, reason = "GIRLS_LUMP_SUM", RATES["CONCESSION"], "Girls lump-sum fee"
    elif category == "OPEN" and has_ebc_ews_certificate:
        group, amount, reason = "OBC_EBC_EWS", RATES["OBC_EBC_EWS"], "Open with EBC/EWS certificate, matched to OBC net fee"
    elif category in {"OBC", "EBC", "EWS", "SBC"}:
        group, amount, reason = "OBC_EBC_EWS", RATES["OBC_EBC_EWS"], "After scholarship deduction"
    elif category in {"ST", "NT(1)", "NT(2)", "NT(3)", "VJ", "DT(A)", "TFWS"}:
        group, amount, reason = "CONCESSION", RATES["CONCESSION"], "Listed concession group"
    elif category == "OPEN":
        group, amount, reason = "OPEN", RATES["OPEN"], "Open full fee"
    else:
        return {"fee_year": LATEST_FEE_YEAR, "fee_group": None, "base_fee": None, "carried_balance": str(balance), "amount_due": None, "needs_staff_confirmation": True, "reason": "Category is not explicitly mapped."}
    return {"fee_year": LATEST_FEE_YEAR, "fee_group": group, "base_fee": str(amount), "carried_balance": str(balance), "amount_due": str(amount + balance), "needs_staff_confirmation": False, "reason": reason}
