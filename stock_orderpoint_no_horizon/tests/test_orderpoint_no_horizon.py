# Copyright 2023 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2025 Camptocamp SA

from datetime import date, datetime, timedelta

from odoo.addons.base.tests.common import BaseCommon


class TestOrderpointNoHorizon(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.product"].create(
            {"name": "Test Orderpoint No Horizon", "is_storable": True}
        )

    def test_reordering_rule_no_horizon(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "name": __name__,
                "warehouse_id": warehouse.id,
                "location_id": warehouse.lot_stock_id.id,
                "route_id": warehouse.reception_route_id.id,
                "product_id": self.product.id,
                "product_min_qty": 0.0,
                "product_max_qty": 5.0,
            }
        )

        # get auto-created pull rule from when warehouse is created
        supplier_loc = self.env.ref("stock.stock_location_suppliers")
        rule = self.env["stock.rule"].search(
            [
                ("route_id", "=", warehouse.reception_route_id.id),
                ("location_dest_id", "=", warehouse.lot_stock_id.id),
                ("location_src_id", "=", supplier_loc.id),
                ("action", "=", "pull"),
                ("procure_method", "=", "make_to_stock"),
                ("picking_type_id", "=", warehouse.in_type_id.id),
            ]
        )
        if not rule:
            # when purchase_stock is installed, the rule is replaced by a buy
            # route, so recreate it
            rule = self.env["stock.rule"].create(
                {
                    "name": "pull",
                    "route_id": warehouse.reception_route_id.id,
                    "location_dest_id": warehouse.lot_stock_id.id,
                    "location_src_id": supplier_loc.id,
                    "action": "pull",
                    "procure_method": "make_to_stock",
                    "picking_type_id": warehouse.in_type_id.id,
                }
            )

        delivery_move = self.env["stock.move"].create(
            {
                "name": "Delivery",
                "date": datetime.today() + timedelta(days=5),
                "product_id": self.product.id,
                "product_uom": self.uom_unit.id,
                "product_uom_qty": 12.0,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.ref("stock.stock_location_customers"),
            }
        )
        delivery_move._action_confirm()

        orderpoint.action_replenish()

        receipt_move = self.env["stock.move"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.env.ref("stock.stock_location_suppliers").id),
            ]
        )
        self.assertTrue(receipt_move)
        self.assertEqual(receipt_move.date.date(), date.today())
        self.assertEqual(receipt_move.product_uom_qty, 17.0)
        self.assertEqual(orderpoint.qty_forecast, orderpoint.product_max_qty)

        # Postpone the reception
        receipt_move.date += timedelta(days=20)
        orderpoint.invalidate_recordset(["qty_forecast"])
        # Check this has no impact no the forecasted quantity
        self.assertEqual(orderpoint.qty_forecast, orderpoint.product_max_qty)
