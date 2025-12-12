# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo.fields import Command
from odoo.tests import Form

from odoo.addons.base.tests.common import BaseCommon


class TestProductReplenish(BaseCommon):
    def test_supplier(self):
        product = self.env["product.product"].create(
            {
                "name": "Test product",
                "type": "consu",
                "is_storable": True,
                "categ_id": self.env.ref("product.product_category_all").id,
                "route_ids": [
                    Command.link(self.env.ref("purchase_stock.route_warehouse0_buy").id)
                ],
            }
        )
        vendor = self.env["res.partner"].create({"name": "vendor"})
        self.env["product.supplierinfo"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "partner_id": vendor.id,
            }
        )
        warehouse = self.env.ref("stock.warehouse0")
        self.env["stock.warehouse.orderpoint"].create(
            {
                "name": "test",
                "warehouse_id": warehouse.id,
                "product_id": product.id,
                "company_id": warehouse.company_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "product_uom": product.uom_id.id,
            }
        )
        replenish_wizard = Form(
            self.env["product.replenish"].with_context(
                default_product_tmpl_id=product.product_tmpl_id.id
            )
        )
        self.assertTrue(replenish_wizard.supplier_id)
