# Copyright 2024 Camptocamp SA
# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = "product.category"

    def write(self, vals):
        if not self or not ("route_ids" in vals or "parent_id" in vals):
            return super().write(vals)

        categ_was_mto = self.filtered(
            lambda c: any(route.is_mto for route in c.total_route_ids)
        )
        if categ_was_mto:
            # Load MTO products as we may need to archive them.
            # A category is not bound to a company, search products accross all
            # companies.
            _logger.debug("Search products already as MTO")
            original_mto_products = (
                self.env["product.product"]
                .sudo()
                .search(
                    [
                        ("categ_id", "child_of", self.ids),
                        ("is_mto", "=", True),
                    ]
                )
            )
        categ_was_not_mto = self - categ_was_mto

        res = super().write(vals)

        categ_is_mto = self.filtered(
            lambda c: any(route.is_mto for route in self.total_route_ids)
        )
        categ_is_not_mto = self - categ_is_mto
        categ_changed_to_mto = categ_was_not_mto & categ_is_mto
        categ_changed_to_not_mto = categ_was_mto & categ_is_not_mto
        # Update orderpoints for MTO / not MTO products that are linked to
        # these categories.
        if categ_changed_to_mto:
            # Update all products to prevent recompute one by one
            # A category is not bound to a company, search products accross all
            # companies.
            _logger.debug("Search products to mark as MTO")
            products = (
                self.env["product.product"]
                .sudo()
                .search([("categ_id", "child_of", categ_changed_to_mto.ids)])
            )
            not_mto_products = products.search(
                [("id", "in", products.ids), ("is_mto", "=", False)]
            )
            _logger.debug(f"Mark {len(not_mto_products)} products as MTO")
            not_mto_products.with_context(orderpoint_mto_as_mts=True).is_mto = True
            _logger.debug("Marked")
            # Populate missing orderpoints
            products._ensure_default_orderpoint_for_mto()
        if categ_changed_to_not_mto:
            original_mto_products._archive_orderpoints_on_mto_removal()
        return res
