# Copyright 2024 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    @api.depends("warehouse_id", "company_id")
    def _compute_location_id(self):
        res = super()._compute_location_id()
        for orderpoint in self:
            warehouse = orderpoint.warehouse_id
            if not warehouse:
                warehouse = orderpoint.env["stock.warehouse"].search(
                    [("company_id", "=", orderpoint.company_id.id)], limit=1
                )
            if warehouse.orderpoint_loc_id:
                orderpoint.location_id = warehouse.orderpoint_loc_id.id
        return res
