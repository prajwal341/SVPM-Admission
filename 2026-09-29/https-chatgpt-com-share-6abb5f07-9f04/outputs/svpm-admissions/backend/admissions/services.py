from decimal import Decimal, InvalidOperation

LATEST_FEE_YEAR = "2025-26"
FEE_GROUPS = {"OPEN": Decimal("89350.00"), "SC": Decimal("350.00"), "CONCESSION": Decimal("10867.00"), "OBC_EBC_EWS": Decimal("50109.00")}


def calculate_latest_fee(*, category: str, gender: str, has_ebc_ews_certificate: bool = False, carried_balance=0):
    """Return the latest rates supplied by the college; these are net amounts where specified."""
    category, gender = category.strip().upper(), gender.strip().upper()
    try:
        balance = Decimal(str(carried_balance))
    except InvalidOperation as exc:
        raise ValueError("Invalid carried balance") from exc
    if balance < 0:
        raise ValueError("Carried balance cannot be negative")

    if category == "SC":
        group, base, reason = "SC", FEE_GROUPS["SC"], "₹350 category"
    elif gender in {"F", "FEMALE"}:
        group, base, reason = "GIRLS_LUMP_SUM", FEE_GROUPS["CONCESSION"], "Girls lump-sum fee"
    elif category == "OPEN" and has_ebc_ews_certificate:
        group, base, reason = "OBC_EBC_EWS", FEE_GROUPS["OBC_EBC_EWS"], "Open with EBC/EWS certificate, matched to OBC net fee"
    elif category in {"OBC", "EBC", "EWS", "SBC"}:
        group, base, reason = "OBC_EBC_EWS", FEE_GROUPS["OBC_EBC_EWS"], "Category fee after scholarship deduction"
    elif category in {"ST", "NT(1)", "NT(2)", "NT(3)", "VJ", "DT(A)", "TFWS"}:
        group, base, reason = "CONCESSION", FEE_GROUPS["CONCESSION"], "Listed concession group"
    elif category == "OPEN":
        group, base, reason = "OPEN", FEE_GROUPS["OPEN"], "Open full fee"
    else:
        return {"fee_year": LATEST_FEE_YEAR, "fee_group": None, "base_fee": None, "carried_balance": str(balance), "amount_due": None, "needs_staff_confirmation": True, "reason": "Category is not explicitly mapped in the supplied fee rules."}

    return {"fee_year": LATEST_FEE_YEAR, "fee_group": group, "base_fee": str(base), "carried_balance": str(balance), "amount_due": str(base + balance), "needs_staff_confirmation": False, "reason": reason}
