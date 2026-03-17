# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from freezegun import freeze_time

from .common import OrderpointSafetyStockCommon


@freeze_time("2026-01-14")
class TestStockOrderpointSafetyStockFixtureSerie01(OrderpointSafetyStockCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = cls._load_serie_from_csv(
            "stock_orderpoint_safety_stock/tests/data/serie_01.csv"
        )
        cls._create_moves_from_serie(cls.product, cls.serie)
        cls.env.company.demand_history_days = 69
        cls.orderpoint.rule_ids.delay = 7
        cls.orderpoint.invalidate_recordset(["lead_days"])

    def test_fixture_serie_01(self):
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 5850.03,
                    "demand_std_dev": 20444.87,
                    "demand_lt_std_dev": 54092.04,
                    "safety_stock": 88976.0,
                    "product_min_qty": 129927.0,
                    "product_max_qty": 129927.0,
                }
            ],
        )

    def test_fixture_serie_01_with_cycle_days(self):
        self.orderpoint.cycle_days = 5
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 5850.03,
                    "demand_std_dev": 20444.87,
                    "demand_lt_std_dev": 54092.04,
                    "safety_stock": 88976.0,
                    # Safety stock + demand avg * lead time (ceiled for unit UoM)
                    "product_min_qty": 129927.0,
                    # Min quantity + demand avg * days to order (ceiled for unit UoM)
                    "product_max_qty": 159177.0,
                }
            ],
        )


class TestStockOrderpointSafetyStockScenarios(OrderpointSafetyStockCommon):
    """Test the safety stock computations with different theoretical scenarios"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.orderpoint.rule_ids.delay = 4
        cls.orderpoint.invalidate_recordset(["lead_days"])

    def test_scenario_product_sold_every_10_days(self):
        """Test the safety stock computations with a product sold every 10 days

        This would be the case of a slow moving product, sold every once in a while.
        """
        self.env.company.demand_history_days = 360
        serie_start = self.today - timedelta(days=360)  # 1 year ago
        serie = [(serie_start + timedelta(days=n * 10), 10) for n in range(36)]
        self._create_moves_from_serie(self.product, serie)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 1,
                    "demand_std_dev": 3,
                    "demand_lt_std_dev": 6,
                    "safety_stock": 9.87,
                    "product_min_qty": 14.0,
                    "product_max_qty": 14.0,
                }
            ],
        )
        # Now let's say lead time is 12 days
        self.orderpoint.rule_ids.delay = 12
        self.orderpoint.invalidate_recordset()
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 1,
                    "demand_std_dev": 3,
                    "demand_lt_std_dev": 10.39,
                    "safety_stock": 17.09,
                    "product_min_qty": 30.0,
                    "product_max_qty": 30.0,
                }
            ],
        )
        # Now let's say lead time is 4 days, but we have 8 cycle days (buffer)
        self.orderpoint.cycle_days = 8
        self.orderpoint.rule_ids.delay = 4
        self.orderpoint.invalidate_recordset()
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 1,
                    "demand_std_dev": 3,
                    "demand_lt_std_dev": 6,
                    "safety_stock": 9.87,
                    "product_min_qty": 14.0,
                    "product_max_qty": 22.0,
                }
            ],
        )

    def test_scenario_product_without_variation(self):
        """Test the safety stock computations with a product without variation

        That is, a product that is sold the same amount every day.
        """
        self.env.company.demand_history_days = 7
        serie = [(self.today - timedelta(days=n + 1), 10) for n in range(7)]
        self._create_moves_from_serie(self.product, serie)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 10,
                    "demand_std_dev": 0,
                    "demand_lt_std_dev": 0,
                    "safety_stock": 0,  # No variation -> no safety stock
                    "product_min_qty": 40,  # demand avg * lead time
                    "product_max_qty": 40,  # cycle days is zero, so max == min
                }
            ],
        )
        # Now let's say we have 7 cycle days (buffer)
        self.orderpoint.cycle_days = 7
        self.orderpoint.invalidate_recordset()
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(
            self.orderpoint,
            [
                {
                    "demand_avg_qty": 10,
                    "demand_std_dev": 0,
                    "demand_lt_std_dev": 0,
                    "safety_stock": 0,
                    "product_min_qty": 40,  # demand avg * lead time
                    "product_max_qty": 110,  # min + demand avg * days to order
                }
            ],
        )
