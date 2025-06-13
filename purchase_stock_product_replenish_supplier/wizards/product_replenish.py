# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo import api, fields, models


class ProductReplenish(models.TransientModel):
    _inherit = "product.replenish"

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        if res.get("product_id"):
            product = self.env["product.product"].browse(res["product_id"])
            suppliers = product.product_tmpl_id.seller_ids.filtered(
                lambda s: s.product_id.id in (product.id, False)
            )
            # FIX odoo bug where default supplier could be for another variant
            if res.get("supplier_id") not in suppliers.ids:
                res["supplier_id"] = False
            # When an orderpoint exists, odoo doesn't set the default supplier
            # if not set on the orderpoint. But it is not required to set a
            # supplier on an orderpoint (the field is even hidden by default),
            # it will default to the main product supplier
            if not res.get("supplier_id") and suppliers:
                res["supplier_id"] = fields.first(suppliers).id
        return res
