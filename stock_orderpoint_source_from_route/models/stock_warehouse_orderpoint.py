# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    location_src_id = fields.Many2one(
        comodel_name="stock.location",
        compute="_compute_location_src_id",
        string="Source Location (from Route)",
        readonly=True,
        help="This is the location computed from the selected route",
    )

    @api.depends("route_id")
    def _compute_location_src_id(self):
        for orderpoint in self:
            location = False
            if orderpoint.route_id:
                location = orderpoint.route_id._get_source_location(
                    orderpoint.location_id
                )
            orderpoint.location_src_id = location
