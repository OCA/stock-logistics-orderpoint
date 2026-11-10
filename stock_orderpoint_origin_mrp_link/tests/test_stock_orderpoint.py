# Copyright 2026 Simone Rubino - PyTech
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields

from odoo.addons.base.tests.common import BaseCommon


class TestOrderpointPurchaseMrpLink(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.vendor = cls.env["res.partner"].create({"name": "Test vendor"})
        cls.product, cls.component = cls.env["product.product"].create(
            [
                {
                    "name": "Test Product",
                    "is_storable": True,
                },
                {
                    "name": "Test Component",
                    "is_storable": True,
                    "route_ids": cls.warehouse.buy_pull_id.route_id.ids,
                    "seller_ids": [
                        fields.Command.create({"partner_id": cls.vendor.id})
                    ],
                },
            ]
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_id": cls.product.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "bom_line_ids": [
                    fields.Command.create({"product_id": cls.component.id}),
                ],
            }
        )

    def test_mo_replenish(self):
        """Create a MO where a component needs to be bought.
        Check that the MO is in the generated Purchase Order's "origin".
        """
        # Arrange
        production = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "bom_id": self.bom.id,
            }
        )
        production.action_confirm()
        # `action_open_orderpoints` creates the missing orderpoints
        self.env["stock.warehouse.orderpoint"].action_open_orderpoints()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.component.id)]
        )
        # pre-condition
        self.assertTrue(orderpoint)

        # Act
        orderpoint.action_replenish()

        # Assert
        purchase_order = self.env["purchase.order"].search(
            [("partner_id", "=", self.vendor.id)]
        )
        self.assertEqual(1, purchase_order.mrp_production_count)
        self.assertIn(production, purchase_order._get_mrp_productions())
        self.assertIn(production.name, purchase_order.origin)
