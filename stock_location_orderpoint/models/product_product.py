# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_domain_locations_new(self, location_ids):
        """Allow restricting the incoming moves considered in the forecast
        via an additional domain passed through the context.

        Used to check whether the demand a not-yet-started replenishment
        move was created for still exists, without letting the move's own
        quantity hide the answer.
        """
        (
            domain_quant_loc,
            domain_move_in_loc,
            domain_move_out_loc,
        ) = super()._get_domain_locations_new(location_ids)
        additional_incoming_moves_domain = self.env.context.get(
            "additional_incoming_moves_domain"
        )
        if additional_incoming_moves_domain:
            domain_move_in_loc = expression.AND(
                [domain_move_in_loc, additional_incoming_moves_domain]
            )
        return domain_quant_loc, domain_move_in_loc, domain_move_out_loc
