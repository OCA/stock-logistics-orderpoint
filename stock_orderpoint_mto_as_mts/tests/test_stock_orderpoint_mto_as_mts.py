# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo.tests import common


class TestStockOrderpointMtoAsMts(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.product_obj = cls.env["product.product"]

        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.warehouse.write(
            {"archive_orderpoints_mto_removal": True, "mto_as_mts": True}
        )
        cls.warehouse1 = cls.env["stock.warehouse"].create(
            {
                "name": "Test Warehouse",
                "code": "TWH",
                "archive_orderpoints_mto_removal": True,
                "mto_as_mts": True,
            }
        )

        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.mto_route.write(
            {
                "active": True,
                "is_mto": True,
            }
        )

    def test_orderpoint(self):
        # Create orderpoint
        product = self.product_obj.create(
            {
                "name": "Test MTO",
                "type": "product",
                "route_ids": [(6, 0, [self.mto_route.id])],
            }
        )
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertTrue(orderpoint)
        self.assertTrue(len(orderpoint) == 2)
        # Archive orderpoint
        product.write({"route_ids": [(6, 0, [])]})
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertFalse(orderpoint)
