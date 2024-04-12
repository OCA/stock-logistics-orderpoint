# Copyright 2024 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestStockOrderpointDefaultWarehouseLocation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.product_obj = cls.env["product.product"]
        cls.orderpoint_obj = cls.env["stock.warehouse.orderpoint"]
        cls.loc_obj = cls.env["stock.location"]

        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.stock_loc = cls.env.ref("stock.stock_location_stock")

        # Prepare Products:
        cls.product = cls.product_obj.create({"name": "Test Product"})

        # Create a new locations and routes:
        cls.orderpoint_loc = cls.loc_obj.create(
            {
                "name": "Orderpoint location 1",
                "usage": "internal",
                "location_id": cls.warehouse.view_location_id.id,
            }
        )

    def test_01(self):
        """Get location of orderpoint from orderpoint_loc_id"""
        self.warehouse.orderpoint_loc_id = self.orderpoint_loc
        orderpoint = self.orderpoint_obj.create(
            {
                "warehouse_id": self.warehouse.id,
                "product_id": self.product.id,
                "product_min_qty": 10.0,
                "product_max_qty": 50.0,
                "product_uom": self.product.uom_id.id,
            }
        )
        self.assertTrue(orderpoint.location_id, self.orderpoint_loc)

    def test_02(self):
        """Get location of orderpoint from lot_stock_id"""
        orderpoint = self.orderpoint_obj.create(
            {
                "warehouse_id": self.warehouse.id,
                "product_id": self.product.id,
                "product_min_qty": 10.0,
                "product_max_qty": 50.0,
                "product_uom": self.product.uom_id.id,
            }
        )
        self.assertTrue(orderpoint.location_id, self.stock_loc)
