# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _merge_moves_fields(self):
        # Make sure to link to the highest-priority orderpoint.

        # This ensures the merged move inherits the correct priority
        res = super()._merge_moves_fields()
        res["location_orderpoint_id"] = max(
            self, key=lambda x: x.location_orderpoint_id.priority
        ).location_orderpoint_id
        return res
