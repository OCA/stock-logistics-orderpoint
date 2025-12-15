# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    qty_to_order_source_not_available = fields.Float(
        compute="_compute_qty_to_order",
    )

    @api.depends("route_id.orderpoint_source_limit_available")
    def _compute_qty_to_order(self):
        res = super()._compute_qty_to_order()
        for orderpoint in self:
            orderpoint.qty_to_order_source_not_available = orderpoint.qty_to_order
            if (
                orderpoint.qty_to_order
                and orderpoint.route_id.orderpoint_source_limit_available
            ):
                orderpoint.qty_to_order = min(
                    orderpoint.qty_to_order,
                    orderpoint.product_id.with_context(
                        location=orderpoint.location_src_id.id
                    ).virtual_available,
                )
        return res
