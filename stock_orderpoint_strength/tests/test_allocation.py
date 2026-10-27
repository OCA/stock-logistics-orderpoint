# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import BaseCase

from odoo.addons.stock_orderpoint_strength.models.stock_move import Claim, allocate


class TestAllocation(BaseCase):
    def test_proportional_split(self):
        claims = [
            Claim("A", requested=15, weight=1, increment=1),
            Claim("B", requested=15, weight=2, increment=1),
        ]
        self.assertEqual(allocate(claims, 6), {"A": 2, "B": 4})

    def test_cap_and_redistribute(self):
        claims = [
            Claim("A", requested=15, weight=1, increment=1),
            Claim("B", requested=15, weight=2, increment=1),
        ]
        self.assertEqual(allocate(claims, 23), {"A": 8, "B": 15})

    def test_factor_below_1(self):
        claims = [
            Claim("A", requested=10, weight=1, increment=1),
            Claim("B", requested=10, weight=0.5, increment=1),
        ]
        self.assertEqual(allocate(claims, 6), {"A": 4, "B": 2})

    def test_indivisible_increment(self):
        claims = [
            Claim("A", requested=30, weight=1, increment=10),
            Claim("B", requested=30, weight=1, increment=10),
        ]
        self.assertEqual(allocate(claims, 12), {"A": 10, "B": 0})

    def test_total_never_exceeds_available(self):
        claims = [
            Claim("A", requested=17, weight=3, increment=4),
            Claim("B", requested=11, weight=1, increment=3),
        ]
        result = allocate(claims, 13)
        self.assertLessEqual(sum(result.values()), 13)
        for claim in claims:
            self.assertLessEqual(result[claim.id], claim.requested)
            units = result[claim.id] / claim.increment
            self.assertAlmostEqual(units, round(units))
