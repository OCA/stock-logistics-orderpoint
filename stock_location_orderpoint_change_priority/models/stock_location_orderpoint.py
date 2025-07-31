# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockLocationOrderpoint(models.Model):
    _inherit = "stock.location.orderpoint"

    def run_replenishment(self, products=False):
        replenishment_moves = super().run_replenishment()
        for move in replenishment_moves:
            move.priority = move.location_orderpoint_id.priority
        return replenishment_moves
