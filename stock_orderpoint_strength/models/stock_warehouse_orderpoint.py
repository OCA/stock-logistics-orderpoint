# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _get_strength_rounding_increment(self):
        """The smallest quantity worth allocating, in the product's own unit.

        One whole unit unless the rule names a Replenishment UoM, in which case
        one of those. A share of two thirds of a unit serves nobody, and Odoo
        19 no longer keeps a rounding precision per unit of measure to say so:
        `uom.rounding` is the same "Product Unit" precision for every unit
        there is.
        """
        self.ensure_one()
        uom = self.replenishment_uom_id or self.product_id.uom_id
        return uom._compute_quantity(1, self.product_id.uom_id)
