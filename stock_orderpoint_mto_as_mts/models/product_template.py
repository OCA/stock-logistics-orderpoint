# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        template = super().create(vals_list)
        template.product_variant_ids._ensure_default_orderpoint_for_mto()
        return template

    def write(self, vals):
        if self.env.context.get("orderpoint_mto_as_mts"):
            return super().write(vals)
        if "route_ids" in vals or "categ_id" in vals:
            original_mto_products = self.product_variant_ids.filtered("is_mto")
        res = super().write(vals)
        if "company_id" in vals:
            # Change company, must archive orderpoints
            self.product_variant_ids.sudo()._archive_orderpoints_on_mto_removal(
                forceall=True
            )
            self.product_variant_ids._ensure_default_orderpoint_for_mto()
        elif "route_ids" in vals or "categ_id" in vals:
            # is_mto may have changed
            original_mto_products._archive_orderpoints_on_mto_removal()
            original_not_mto_products = self.product_variant_ids - original_mto_products
            original_not_mto_products._ensure_default_orderpoint_for_mto()
        return res
