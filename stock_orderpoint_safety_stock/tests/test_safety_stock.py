# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.tests import Form

from .common import OrderpointSafetyStockCommon


class TestStockOrderpointSafetyStock(OrderpointSafetyStockCommon):
    """Test the safety stock computations with a small and understandable example

    In general, we use a 7 days window, with only these moves:
    - 6d ago: 10 + 5 out
    - 4d ago: 12 out

    Lead time is 1 day.

    Specific tests will build on this example.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.demand_history_days = 7
        cls.orderpoint.rule_ids.delay = 1
        cls.orderpoint.invalidate_recordset(["lead_days"])
        cls.moves = cls._create_moves_from_serie(
            cls.product,
            [
                (cls.today - timedelta(days=6), 10),
                (cls.today - timedelta(days=6), 5),
                (cls.today - timedelta(days=4), 12),
                (cls.today, 10),  # Will be ignored, as today's not finished
            ],
        )
        cls.default_serie = [0, 15, 0, 12, 0, 0, 0]

    def test_math_simple(self):
        """Test the math on a small and understandable example"""
        serie = self.default_serie
        expected = self._compute_values(serie, round_min_max_to_unit=True)
        self.orderpoint.action_apply_safety_stock()
        self.assertEqual(self._get_orderpoint_serie(self.orderpoint), serie)
        self.assertRecordValues(self.orderpoint, [expected])

    def test_growth_factor(self):
        """Test that a non-zero growth_factor scales the stock levels correctly.

        Same serie as test_math_simple. growth_factor=0.5 means the multiplier
        in the formula becomes (1.0 + 0.5) = 1.5.
        """
        self.orderpoint.growth_factor = 0.5
        serie = self.default_serie
        expected = self._compute_values(serie, growth=0.5, round_min_max_to_unit=True)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(self.orderpoint, [expected])

    def test_assigned_partially_assigned_confirmed_moves(self):
        """Test that moves in all four counted states contribute to demand.

        The domain includes states: assigned, confirmed, partially_available, done.
        We create one move per state and verify all four are aggregated.
        """
        self.env["stock.move"].create(
            [
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 8,
                    "date": self.today - timedelta(days=5),
                    "location_id": self.warehouse.lot_stock_id.id,
                    "location_dest_id": self.customer_location.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "assigned",
                    "picked": True,
                    "quantity": 8,
                },
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 10,
                    "date": self.today - timedelta(days=4),
                    "location_id": self.warehouse.lot_stock_id.id,
                    "location_dest_id": self.customer_location.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "partially_available",
                    "picked": True,
                    "quantity": 4,
                },
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 6,
                    "date": self.today - timedelta(days=3),
                    "location_id": self.warehouse.lot_stock_id.id,
                    "location_dest_id": self.customer_location.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "confirmed",
                    "quantity": 0,
                },
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 12,
                    "date": self.today - timedelta(days=2),
                    "location_id": self.warehouse.lot_stock_id.id,
                    "location_dest_id": self.customer_location.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "done",
                    "quantity": 12,
                },
            ]
        )
        # Test serie
        serie = [0, 15, (0 + 8), (12 + 10), (0 + 6), (0 + 12), 0]
        expected = self._compute_values(serie, round_min_max_to_unit=True)
        self.assertEqual(self._get_orderpoint_serie(self.orderpoint), serie)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(self.orderpoint, [expected])

    def test_inventory_adjustments_excluded(self):
        """Test that moves to/from inventory-adjustment locations are excluded.

        The outgoing domain excludes location_dest_id.usage == 'inventory' and
        the incoming domain excludes location_id.usage == 'inventory'.  We create
        normal outgoing moves alongside inventory-adjustment moves and verify only
        the normal moves are counted.
        """
        # Create a few inventory adjustment
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "inventory_quantity": 2000,
                "location_id": self.orderpoint.location_id.id,
            }
        ).action_apply_inventory(date=self.today - timedelta(days=6))
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "inventory_quantity": 500,
                "location_id": self.orderpoint.location_id.id,
            }
        ).action_apply_inventory(date=self.today - timedelta(days=3))
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "inventory_quantity": 20,
                "location_id": self.orderpoint.location_id.id,
            }
        ).action_apply_inventory(date=self.today - timedelta(days=1))
        # Test serie: inventory adjustments are not taken into account
        serie = self.default_serie
        expected = self._compute_values(serie, round_min_max_to_unit=True)
        self.assertEqual(self._get_orderpoint_serie(self.orderpoint), serie)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(self.orderpoint, [expected])

    def test_supplier_incoming_moves_excluded(self):
        """Test that supplier incoming moves are excluded.

        A supplier incoming move is a move from a supplier to the warehouse.
        It's not considered a demand.
        """
        supplier_location = self.env.ref("stock.stock_location_suppliers")
        self.env["stock.move"].create(
            [
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 10,
                    "date": self.today - timedelta(days=3),
                    "location_id": supplier_location.id,
                    "location_dest_id": self.warehouse.lot_stock_id.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "done",
                    "quantity": 10,
                },
            ]
        )
        # Test serie: supplier incoming moves are not taken into account
        serie = self.default_serie
        expected = self._compute_values(serie, round_min_max_to_unit=True)
        self.assertEqual(self._get_orderpoint_serie(self.orderpoint), serie)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(self.orderpoint, [expected])

    def test_inter_warehouse_moves(self):
        """Test that inter-warehouse moves are counted correctly per warehouse.

        A move from WH1 stock to WH2 stock is outgoing for WH1.
        It's considered a demand for WH1 but not for WH2.
        """
        warehouse2 = self.env["stock.warehouse"].create(
            {"name": "Warehouse 2", "code": "WH2"}
        )
        orderpoint2 = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product.id,
                "warehouse_id": warehouse2.id,
                "safety_stock_method": "csl",
                "cycle_service_level_id": self.csl_95.id,
            }
        )
        self.env["stock.move"].create(
            [
                # Inter-warehouse: WH1 → WH2 (out for WH1, in for WH2)
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 10,
                    "date": self.today - timedelta(days=3),
                    "location_id": self.warehouse.lot_stock_id.id,
                    "location_dest_id": warehouse2.lot_stock_id.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "done",
                    "quantity": 10,
                },
            ]
        )
        # Test serie for WH1
        serie_wh1 = [0, 15, 0, 12, 10, 0, 0]
        expected_wh1 = self._compute_values(serie_wh1, round_min_max_to_unit=True)
        self.assertEqual(self._get_orderpoint_serie(self.orderpoint), serie_wh1)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(self.orderpoint, [expected_wh1])
        # Test serie for WH2: the incoming move is not counted as demand
        serie_wh2 = [0, 0, 0, 0, 0, 0, 0]
        expected_wh2 = self._compute_values(serie_wh2, round_min_max_to_unit=True)
        self.assertEqual(self._get_orderpoint_serie(orderpoint2), serie_wh2)
        orderpoint2.action_apply_safety_stock()
        self.assertRecordValues(orderpoint2, [expected_wh2])

    def test_different_uoms(self):
        """Test that UoM is correctly used in the safety stock computation"""
        self.env["stock.move"].create(
            [
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "product_uom": self.env.ref("uom.product_uom_pack_6").id,
                    "date": self.today - timedelta(days=3),
                    "location_id": self.warehouse.lot_stock_id.id,
                    "location_dest_id": self.customer_location.id,
                    "company_id": self.warehouse.company_id.id,
                    "state": "done",
                    "quantity": 1,
                },
            ]
        )
        # Test serie: the move is counted as 6 units
        serie = [0, 15, 0, 12, 6, 0, 0]
        expected = self._compute_values(serie, round_min_max_to_unit=True)
        self.assertEqual(self._get_orderpoint_serie(self.orderpoint), serie)
        self.orderpoint.action_apply_safety_stock()
        self.assertRecordValues(self.orderpoint, [expected])

    def test_safety_stock_kg_uom_not_rounded_to_units(self):
        """With Kg UoM, min/max quantities are rounded by UoM but not ceiled to integers

        Only orderpoints in unit UoM (or with common reference to unit) get
        math.ceil applied. For Kg, fractional values like 2.5 are kept.
        """
        uom_kg = self.env.ref("uom.product_uom_kgm")
        product_kg = self.env["product.product"].create(
            {
                "name": "Test Product Kg",
                "type": "consu",
                "is_storable": True,
                "uom_id": uom_kg.id,
            }
        )
        orderpoint_kg = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": product_kg.id,
                "warehouse_id": self.warehouse.id,
                "safety_stock_method": "csl",
                "cycle_service_level_id": self.csl_95.id,
            }
        )
        self.env.company.demand_history_days = 7
        orderpoint_kg.rule_ids.delay = 1
        orderpoint_kg.invalidate_recordset(["lead_days"])
        # Demand that yields fractional avg: e.g. 1.5, 2.0, 1.0 kg -> avg 1.5
        self._create_moves_from_serie(
            product_kg,
            [
                (self.today - timedelta(days=6), 1.5),
                (self.today - timedelta(days=4), 2.0),
                (self.today - timedelta(days=2), 1.0),
            ],
        )
        orderpoint_kg.action_apply_safety_stock()
        # With unit UoM we would get ceil(min_qty), ceil(max_qty). With Kg we must
        # get UoM-rounded values that can be fractional (no forced integer).
        self.assertEqual(orderpoint_kg.product_min_qty, 2.04)
        self.assertEqual(orderpoint_kg.product_max_qty, 2.04)

    def test_onchange_safety_stock_method_apply(self):
        """Test that the safety stock is correctly applied when the method is changed"""
        # Start with a manual orderpoint with some predefined values
        self.orderpoint.safety_stock_method = "manual"
        self.orderpoint.product_min_qty = 10
        self.orderpoint.product_max_qty = 20
        # Change the method to csl and apply the safety stock
        with Form(
            self.orderpoint, view="stock.view_warehouse_orderpoint_tree_editable"
        ) as form:
            form.safety_stock_method = "csl"
            form.cycle_service_level_id = self.csl_95
            expected = self._compute_values(
                self.default_serie, round_min_max_to_unit=True
            )
            self.assertEqual(form.product_min_qty, expected["product_min_qty"])
            self.assertEqual(form.product_max_qty, expected["product_max_qty"])
            # Change the CSL
            form.cycle_service_level_id = self.csl_90
            expected = self._compute_values(
                self.default_serie,
                z_score=self.csl_90.z_score,
                round_min_max_to_unit=True,
            )
            self.assertEqual(form.product_min_qty, expected["product_min_qty"])
            self.assertEqual(form.product_max_qty, expected["product_max_qty"])
            # Change the Growth
            form.growth_factor = 0.5
            expected = self._compute_values(
                self.default_serie,
                z_score=self.csl_90.z_score,
                growth=0.5,
                round_min_max_to_unit=True,
            )
            self.assertEqual(form.product_min_qty, expected["product_min_qty"])
            self.assertEqual(form.product_max_qty, expected["product_max_qty"])

    @freeze_time(fields.Datetime.now())
    def test_cron_recompute_safety_stock(self):
        """Test that the cron job recomputes the safety stock correctly"""
        # Start with a last update in the past
        now = fields.Datetime.now()
        self.orderpoint.safety_stock_update_date = now - timedelta(days=1)
        # Call the cron job and assert the progress is notified
        with patch.object(self.env.registry["ir.cron"], "_commit_progress") as mock:
            self.env["stock.warehouse.orderpoint"]._cron_recompute_safety_stock()
            mock.assert_called_once_with(processed=1, remaining=0)
        self.assertEqual(self.orderpoint.safety_stock_update_date, now, "Updated")
        # Call the cron job again, and make sure no records are processed
        with patch.object(self.env.registry["ir.cron"], "_commit_progress") as mock:
            self.env["stock.warehouse.orderpoint"]._cron_recompute_safety_stock()
            mock.assert_called_once_with(processed=0, remaining=0)
