# Copyright 2024 Camptocamp SA
# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

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
        res = super().write(vals)
        # The set of products may have changed after write
        products |= self.product_ids.product_variant_ids
        products |= self.env["product.product"].search(
            [("categ_id", "child_of", self.categ_ids.ids)]
        )
        if vals["is_mto"]:
            products._ensure_default_orderpoint_for_mto()
        else:
            products._archive_orderpoints_on_mto_removal()
        return res
