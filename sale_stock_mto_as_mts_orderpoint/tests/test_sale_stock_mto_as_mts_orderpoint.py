# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo.tests import Form

from odoo.addons.base.tests.common import BaseCommon


class TestSaleStockMtoAsMtsOrderpoint(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env.ref("base.res_partner_2")
        cls.product = cls.env["product.product"].create(
            {"name": "Test MTO", "type": "consu", "is_storable": True}
        )
        cls.vendor_partner = cls.env.ref("base.res_partner_12")
        cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor_partner.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "min_qty": 1.0,
                "price": 1.0,
            }
        )

        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.warehouse.mto_as_mts = True
        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.buy_route = cls.env.ref("purchase_stock.route_warehouse0_buy")
        cls.product.product_tmpl_id.write(
            {"route_ids": [(6, 0, [cls.mto_route.id, cls.buy_route.id])]}
        )

    @classmethod
    def _create_sale_order(cls):
        sale_form = Form(cls.env["sale.order"])
        sale_form.partner_id = cls.partner
        sale_form.warehouse_id = cls.warehouse
        with sale_form.order_line.new() as line_form:
            line_form.product_id = cls.product
            line_form.product_uom_qty = 1
        return sale_form.save()

    def test_mto_as_mts_orderpoint(self):
        order = self._create_sale_order()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertFalse(orderpoint)
        order.action_confirm()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )

        self.assertEqual(
            orderpoint.location_id,
            self.warehouse._get_locations_for_mto_orderpoints(),
        )
        self.assertAlmostEqual(orderpoint.product_min_qty, 0.0)
        self.assertAlmostEqual(orderpoint.product_max_qty, 0.0)
        self.product.product_tmpl_id.write({"route_ids": [(5, 0, 0)]})
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertFalse(orderpoint)
        orderpoint = (
            self.env["stock.warehouse.orderpoint"]
            .with_context(active_test=False)
            .search([("product_id", "=", self.product.id)])
        )
        self.assertTrue(orderpoint)

    def test_mtp_as_mts_orderpoint_product_no_mto(self):
        self.product.product_tmpl_id.route_ids = False
        order = self._create_sale_order()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertFalse(orderpoint)
        order.action_confirm()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertFalse(orderpoint)

    def test_cancel_sale_order_orderpoint(self):
        order = self._create_sale_order()
        order.action_confirm()
        order.with_context(disable_cancel_warning=True).action_cancel()
        order.action_draft()
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_confirm_mto_as_mts_sudo_needed(self):
        """Check access right needed to confirm sale.

        A sale manager user with no right on inventory will raise an access
        right error on confirmation.
        This is the why of the sudo in `sale_stock_mto_as_mts_orderpoint`
        """
        user = self.env.ref("base.user_demo")
        sale_group = self.env.ref("sales_team.group_sale_manager")
        sale_group.users = [(4, user.id)]
        order = self._create_sale_order()
        order.with_user(user).action_confirm()
