# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockRoute(models.Model):
    _inherit = "stock.route"

    def write(self, vals):
        if "is_mto" not in vals:
            return super().write(vals)
        products = self.product_ids.product_variant_ids
        products |= self.env["product.product"].search(
            [("categ_id", "child_of", self.categ_ids.ids)]
        )
        products = products.with_context(orderpoint_mto_as_mts=True)
        if vals["is_mto"]:
            products.is_mto = True
        else:
            mto_routes = self.env["stock.route"].search([("is_mto", "=", True)])
            if not mto_routes:
                # When the last mto route is unflagged
                products.is_mto = False
        return super().write(vals)
