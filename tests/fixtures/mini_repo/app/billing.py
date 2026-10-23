"""Billing calculations and invoice generator."""

def _clamp_total(val: float) -> float:
    """Enforce lower numeric floor on currency values."""
    if val < 0.0:
        return 0.0
    return float(val)

def calculate_tax(amount: float, rate: float = 0.05) -> float:
    """Compute local tax charge."""
    return round(amount * rate, 2)

def create_invoice(items: list) -> dict:
    """Generate basic invoice representation."""
    raw_sum = sum(items)
    tax = calculate_tax(raw_sum)
    return {"subtotal": raw_sum, "tax": tax, "final": raw_sum + tax}

def apply_discount(total: float, pct: float) -> float:
    """Apply discount percentage reduction to total amount."""
    cut = total * (pct / 100.0)
    adjusted = total - cut
    clamped = _clamp_total(adjusted)
    return clamped
