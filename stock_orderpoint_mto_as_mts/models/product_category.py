# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    product_ids = fields.One2many("product.product", "categ_id", string="Products")

    def write(self, vals):
        # Override this method to update order points for MTO / not MTO products
        # that linked to these categories

        if not vals.get("route_ids", False):
            # No changes for MTO routes, so no changes for is_mto on products
            res = super().write(vals)
            self.product_ids.sudo()._ensure_default_orderpoint_for_mto()
            return res

        original_mto_products = self.product_ids.filtered(
            lambda product: product.is_mto
        )
        res = super().write(vals)
        self.product_ids.sudo()._ensure_default_orderpoint_for_mto()

        # Find all MTO products that have been changed to Not MTO
        not_mto_product = self.product_ids.filtered(lambda product: not product.is_mto)
        product_to_update = original_mto_products & not_mto_product
        if product_to_update:
            # Archive order points
            product_to_update._archive_orderpoints_on_mto_removal()
        return res
