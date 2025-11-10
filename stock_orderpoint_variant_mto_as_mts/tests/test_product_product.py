# Copyright 2020 Camptocamp SA
# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2025 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestStockOrderpointMtoAsMts(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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

    def test_orderpoint_with_product(self):
        # Create orderpoint
        product = self.env["product.product"].create(
            {
                "name": "Test MTO",
                "type": "consu",
                "is_storable": True,
                "route_ids": [(6, 0, [self.mto_route.id])],
                "is_mto": True,
            }
        )
        orderpoints = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertTrue(orderpoints)
        self.assertEqual(len(orderpoints), 2)
        # Ensure orderpoints are created with correct values
        orderpoint = orderpoints[0]
        self.assertEqual(orderpoint.product_min_qty, 0)
        self.assertEqual(orderpoint.product_max_qty, 0)
        self.assertEqual(orderpoint.trigger, "auto")
        # Archive orderpoint
        product.write({"is_mto": False})
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertFalse(orderpoint)
