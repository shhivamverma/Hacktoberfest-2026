"""Tests for billing and invoicing."""
from app.billing import apply_discount, calculate_tax, create_invoice

def test_apply_discount_caps():
    """Test applying discount capping behavior for extreme percentages."""
    capped = apply_discount(100.0, 150.0)
    assert capped == 0.0

def test_calculate_tax_rounding():
    """Verify tax rounding on invoice total amounts."""
    val = calculate_tax(19.99, 0.075)
    assert val == 1.50

def test_create_invoice_total_amount():
    """Verify invoice generation calculates correct total amount."""
    inv = create_invoice([10.0, 20.0])
    assert inv["total"] > 30.0
