# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):

    _inherit = "product.product"

    def _get_domain_locations_new(self, location_ids):
        (_q, domain_move_in_loc, _ol) = super()._get_domain_locations_new(location_ids)

        if orderpoint_id := self.env.context.get("orderpoint_id"):
            orderpoint = self.env["stock.location.orderpoint"].browse(orderpoint_id)

            domain_move_in_loc = expression.AND(
                [
                    domain_move_in_loc,
                    [
                        ("location_orderpoint_id", "!=", orderpoint.id),
                        ("location_orderpoint_id.priority", ">=", orderpoint.priority),
                    ],
                ]
            )
        return (_q, domain_move_in_loc, _ol)
