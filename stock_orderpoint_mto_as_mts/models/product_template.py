# Copyright 2024
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        template = super().create(vals_list)
        template.product_variant_ids.sudo()._ensure_default_orderpoint_for_mto()
        return template

    def write(self, vals):
        original_mto_templates = self.filtered(lambda temp: temp.is_mto)
        res = super().write(vals)
        self.product_variant_ids.sudo()._ensure_default_orderpoint_for_mto()
        self._update_mto_templates(original_mto_templates, vals)
        return res

    def _update_mto_templates(self, original_mto_templates, vals):
        if "company_id" in vals:
            # Change company, must archive orderpoints
            self.product_variant_ids.sudo()._archive_orderpoints_on_mto_removal()
            self.product_variant_ids.sudo()._ensure_default_orderpoint_for_mto()
            return
        elif "route_ids" not in vals and "categ_id" not in vals:
            # No changes about is_mto
            self.product_variant_ids.sudo()._ensure_default_orderpoint_for_mto()
            return

        not_mto_templates = self.filtered(lambda temp: not temp.is_mto)
        # Find all MTO templates that have been changed to Not MTO
        templates_to_update = original_mto_templates & not_mto_templates
        if templates_to_update:
            # Archive order points
            templates_to_update.product_variant_ids._archive_orderpoints_on_mto_removal()
        return
