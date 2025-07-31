# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.osv import expression


class StockLocationOrderpoint(models.Model):
    _inherit = "stock.location.orderpoint"

    def _find_current_replenishment_moves_for_orderpoint_location(self, products=False):
        self.ensure_one()
        domain = [
            ("location_dest_id", "child_of", self.location_id.id),
            ("priority", "<", self.priority),
            ("state", "not in", ["cancel", "done"]),
            ("location_orderpoint_id", "!=", False),
        ]
        if products:
            domain = expression.AND([domain, [("product_id", "in", products.ids)]])

        return self.env["stock.move"].search(domain)

    def run_replenishment(self, products=False):
        res = super().run_replenishment()
        # When an outgoing stock move triggers a replenishment move, one of three outcomes occurs:
        # 1. A new, independent replenishment move is generated.
        # 2. A new replenishment move is generated, but Odoo's stock logic merges it with an
        #    already existing replenishment move (e.g., for the same product and route).
        # 3. No new replenishment move is created because existing replenishment moves
        #    are already sufficient to satisfy the demand.
        #
        # This code block ensures that in scenario #3, if the orderpoint's priority has changed
        # (e.g., to 'urgent'), the priority of the *existing* sufficient replenishment move is
        # correctly updated. This update is intentionally delayed until after any move merging
        # (relevant for scenario #2) has occurred, preventing information loss before reaching moves
        # merging code (we do not want to overwrite the "previous priority" too early).

        for orderpoint in self:
            replenishment_moves = (
                orderpoint._find_current_replenishment_moves_for_orderpoint_location(
                    products=products
                )
            )

            if replenishment_moves:
                replenishment_moves.write(
                    {
                        "priority": orderpoint.priority,
                    }
                )

        return res
