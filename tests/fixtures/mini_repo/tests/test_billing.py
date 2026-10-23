"""Tests for billing and invoicing."""
from app.billing import apply_discount, calculate_tax

def test_apply_discount_caps():
    capped = apply_discount(100.0, 150.0)
    assert capped == 0.0

def test_calculate_tax_rounding():
    val = calculate_tax(19.99, 0.075)
    assert val == 1.50
