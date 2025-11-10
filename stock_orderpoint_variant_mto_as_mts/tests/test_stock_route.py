# Copyright 2025 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestStockRouteMtoAsMts(BaseCommon):
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
        cls.other_mto_routes = cls.env["stock.route"].search(
            [("is_mto", "=", True), ("id", "!=", cls.mto_route.id)]
        )
        cls.other_mto_routes.is_mto = False

    def _create_mto_product(self):
        return self.env["product.product"].create(
            {
                "name": "Test MTO",
                "type": "consu",
                "is_storable": True,
                "route_ids": [(6, 0, [self.mto_route.id])],
            }
        )

    def test_is_mto_reset_on_last_mto_route_unflagged(self):
        product = self._create_mto_product()
        self.assertTrue(product.is_mto)
        orderpoints = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertEqual(len(orderpoints), 2)
        self.mto_route.is_mto = False
        self.assertFalse(product.is_mto)
        orderpoints = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertFalse(orderpoints)

    def test_is_mto_kept_when_another_mto_route_remains(self):
        product = self._create_mto_product()
        remaining_route = self.env["stock.route"].create(
            {"name": "Other MTO", "is_mto": True}
        )
        orderpoints = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertEqual(len(orderpoints), 2)
        self.mto_route.is_mto = False
        self.assertTrue(remaining_route.is_mto)
        self.assertTrue(product.is_mto)
        orderpoints = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)]
        )
        self.assertEqual(len(orderpoints), 2)
