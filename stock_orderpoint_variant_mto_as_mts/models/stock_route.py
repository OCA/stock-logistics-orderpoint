# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockRoute(models.Model):
    _inherit = "stock.route"

    def write(self, vals):
        if "is_mto" not in vals:
            return super().write(vals)
        if vals["is_mto"]:
            products = self.product_ids.product_variant_ids
            products |= self.env["product.product"].search(
                [("categ_id", "child_of", self.categ_ids.ids)]
            )
            # flag before super() so that stock_orderpoint_mto_as_mts creates
            # the orderpoints on the route write
            products.with_context(orderpoint_mto_as_mts=True).is_mto = True
            return super().write(vals)
        # exclude self: it is still flagged as MTO until super().write
        remaining_mto_routes = self.env["stock.route"].search(
            [("is_mto", "=", True), ("id", "not in", self.ids)]
        )
        res = super().write(vals)
        if not remaining_mto_routes:
            # when the last mto route is unflagged, no product can be mto anymore
            self.env["product.product"].search([("is_mto", "=", True)]).is_mto = False
        return res
