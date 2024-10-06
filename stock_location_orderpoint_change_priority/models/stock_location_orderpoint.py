# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import models
from odoo.osv import expression


class StockLocationOrderpoint(models.Model):

    _inherit = "stock.location.orderpoint"

    def _find_current_replenishment_moves_for_orderpoint_location(self, products=False):
        """ """
        domain = [
            ("location_dest_id", "child_of", self.location_id.id),
            ("priority", "<", self.priority),
            ("state", "not in", ["cancel", "done"]),
            ("location_orderpoint_id", "!=", False),
        ]
        if products:
            domain = expression.AND([domain, [("product_id", "in", products.ids)]])
        move_res = self.env["stock.move"].read_group(
            domain,
            ["ids:array_agg(id)", "product_id"],
            ["location_id", "product_id"],
        )
        location_obj = self.env["stock.location"]
        result = defaultdict(self.env["stock.location"].browse)
        for res in move_res:
            result[location_obj.browse(res.get("location_id")[0])] = self.env[
                "stock.move"
            ].browse(res.get("ids"))
        return result

    def _before_procurement_run(self, procurements=False, products=False):
        """
        This method is called in order:
            - To update existing replenishment moves priority

        We consider the orderpoint has been triggered, so we need
        """
        replenishment_moves_to_update = self.env["stock.move"].browse()
        if not products:
            products = self.env["product.product"].browse()
        for orderpoint in self:
            replenishment_moves_by_location = (
                orderpoint._find_current_replenishment_moves_for_orderpoint_location(
                    products=products
                )
            )

            for (
                __location,
                replenishment_moves,
            ) in replenishment_moves_by_location.items():
                replenishment_moves_to_update |= replenishment_moves

            if replenishment_moves_to_update:
                replenishment_moves_to_update.write(
                    {
                        "priority": orderpoint.priority,
                    }
                )
