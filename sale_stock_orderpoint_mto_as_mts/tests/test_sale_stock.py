# Copyright 2026 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo.tests.common import Form, TransactionCase


class TestSaleStockOrderpointMtoAsMts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env.ref("base.res_partner_2")
        cls.product = cls.env["product.product"].create(
            {"name": "Test MTO", "type": "product"}
        )
        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.mto_route.sale_selectable = True
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.warehouse.mto_as_mts = True
        cls.vendor_partner = cls.env.ref("base.res_partner_12")
        cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor_partner.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "min_qty": 1.0,
                "price": 1.0,
            }
        )

    @classmethod
    def _create_sale_order(cls):
        sale_form = Form(cls.env["sale.order"])
        sale_form.partner_id = cls.partner
        with sale_form.order_line.new() as line_form:
            line_form.product_id = cls.product
            line_form.product_uom_qty = 1
        return sale_form.save()

    def test_so_without_mto(self):
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

    def test_so_with_route_mto(self):
        order = self._create_sale_order()
        order.order_line.route_id = self.mto_route
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertFalse(orderpoint)
        order.action_confirm()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertTrue(orderpoint)

    def test_so_with_wh_route_mto(self):
        order = self._create_sale_order()
        order.warehouse_id.delivery_route_id.is_mto = True
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertFalse(orderpoint)
        order.action_confirm()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertTrue(orderpoint)
