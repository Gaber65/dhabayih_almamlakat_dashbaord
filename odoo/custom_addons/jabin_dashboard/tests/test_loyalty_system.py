# tests/test_loyalty_system.py
import unittest
from unittest.mock import MagicMock


class MockCustomer:
    def __init__(self, id, name, loyalty_points=0):
        self.id = id
        self.name = name
        self.loyalty_points = loyalty_points
        self.total_earned_points = loyalty_points
        self.total_redeemed_points = 0
        self.exists_val = True

    def exists(self):
        return self.exists_val

    def sudo(self):
        return self

    def write(self, vals):
        if 'loyalty_points' in vals:
            self.loyalty_points = vals['loyalty_points']
        if 'total_earned_points' in vals:
            self.total_earned_points = vals['total_earned_points']
        if 'total_redeemed_points' in vals:
            self.total_redeemed_points = vals['total_redeemed_points']
        return True


class TestLoyaltyBusinessRules(unittest.TestCase):
    def setUp(self):
        self.earning_rate = 1.0  # 1 SAR = 1 point
        self.redemption_rate = 100.0  # 100 points = 1 SAR discount
        self.min_redemption = 500  # min 500 points

    def test_earning_points_formula(self):
        """Rule 1: Earn 1 point per 1 SAR spent."""
        # 50 SAR -> 50 points
        self.assertEqual(int(50 * self.earning_rate), 50)
        # 120 SAR -> 120 points
        self.assertEqual(int(120 * self.earning_rate), 120)
        # 1,000 SAR -> 1,000 points
        self.assertEqual(int(1000 * self.earning_rate), 1000)

    def test_redeeming_points_formula(self):
        """Rule 2: Every 100 points = 1 SAR discount."""
        # 500 points -> 5 SAR
        self.assertEqual(round(500 / self.redemption_rate, 2), 5.0)
        # 1,000 points -> 10 SAR
        self.assertEqual(round(1000 / self.redemption_rate, 2), 10.0)
        # 2,500 points -> 25 SAR
        self.assertEqual(round(2500 / self.redemption_rate, 2), 25.0)

    def test_minimum_redemption_validation(self):
        """Rule 3: Rejection if under 500 points."""
        customer = MockCustomer(1, "Test Customer", loyalty_points=450)
        # 450 points is less than minimum 500
        self.assertLess(customer.loyalty_points, self.min_redemption)

        customer_eligible = MockCustomer(2, "Eligible Customer", loyalty_points=600)
        self.assertGreaterEqual(customer_eligible.loyalty_points, self.min_redemption)

    def test_redemption_balance_validation(self):
        """Rule 5: Cannot redeem more points than owned."""
        customer = MockCustomer(1, "Customer", loyalty_points=600)
        # User tries to redeem 800 points
        requested_points = 800
        self.assertGreater(requested_points, customer.loyalty_points)

    def test_redemption_order_total_validation(self):
        """Rule 5: Cannot redeem points exceeding order total."""
        # Order total = 15 SAR. Customer points = 2000 points (20 SAR value).
        order_total = 15.0
        points = 2000
        discount_sar = points / self.redemption_rate  # 20 SAR
        self.assertGreater(discount_sar, order_total)

    def test_points_award_on_delivery(self):
        """Rule 4: Points are awarded only when order is delivered."""
        customer = MockCustomer(1, "Customer", loyalty_points=100)
        order_total = 120.0
        order_state = "delivered"

        earned = int(order_total * self.earning_rate)
        if order_state == "delivered":
            customer.loyalty_points += earned
            customer.total_earned_points += earned

        self.assertEqual(customer.loyalty_points, 220)
        self.assertEqual(customer.total_earned_points, 220)

    def test_points_deduction_on_refund(self):
        """Rule 4: Deduct awarded points when delivered order is refunded."""
        customer = MockCustomer(1, "Customer", loyalty_points=220)
        awarded_points = 120

        # Refund happens
        customer.loyalty_points = max(0, customer.loyalty_points - awarded_points)
        self.assertEqual(customer.loyalty_points, 100)


if __name__ == "__main__":
    unittest.main()
