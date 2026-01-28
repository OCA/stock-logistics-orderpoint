# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from .common import OrderpointSafetyStockCommon


class TestCycleServiceLevel(OrderpointSafetyStockCommon):
    def test_known_z_scores(self):
        self.assertAlmostEqual(self.csl_90.z_score, 1.2816, places=4)
        self.assertAlmostEqual(self.csl_95.z_score, 1.6449, places=4)
        self.assertAlmostEqual(self.csl_97.z_score, 1.8808, places=4)
        self.assertAlmostEqual(self.csl_99.z_score, 2.3263, places=4)

    def test_orderpoint_count(self):
        self.assertEqual(self.csl_95.orderpoint_count, 1)
        self.assertEqual(self.csl_97.orderpoint_count, 0)
        self.orderpoint.cycle_service_level_id = self.csl_97
        self.assertEqual(self.csl_95.orderpoint_count, 0)
        self.assertEqual(self.csl_97.orderpoint_count, 1)

    def test_action_open_orderpoints(self):
        action = self.csl_95.action_open_orderpoints()
        orderpoints = self.env["stock.warehouse.orderpoint"].search(action["domain"])
        self.assertEqual(orderpoints, self.orderpoint)
        self.assertEqual(action["context"].get("default_safety_stock_method"), "csl")
        self.assertEqual(
            action["context"].get("default_cycle_service_level_id"), self.csl_95.id
        )
