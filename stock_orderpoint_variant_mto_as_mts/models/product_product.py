# Copyright 2025 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def write(self, vals):
        if self.env.context.get("orderpoint_mto_as_mts"):
            return super().write(vals)
        if "is_mto" in vals:
            original_mto_products = self.filtered("is_mto")
        res = super().write(vals)
        if "is_mto" in vals:
            # is_mto may have changed
            original_mto_products._archive_orderpoints_on_mto_removal()
            original_not_mto_products = self - original_mto_products
            original_not_mto_products._ensure_default_orderpoint_for_mto()
        return res
