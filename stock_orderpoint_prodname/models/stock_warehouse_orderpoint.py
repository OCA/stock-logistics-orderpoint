# © 2024 Solvos Consultoría Informática (<http://www.solvos.es>)
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import api, fields, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    name = fields.Char(required=False, default=None)

    @api.model_create_multi
    def create(self, vals_list):
        products = {vals["product_id"]: "" for vals in vals_list}
        product_ids = self.env["product.product"].browse(list(products.keys()))
        for product in product_ids:
            products[product.id] = product.default_code or product.name
        for vals in vals_list:
            vals["name"] = products[vals["product_id"]]
        return super().create(vals_list)
