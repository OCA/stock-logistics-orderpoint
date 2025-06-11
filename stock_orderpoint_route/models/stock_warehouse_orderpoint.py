# Copyright 2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    route_ids = fields.Many2many(
        "stock.route", string="Allowed routes", compute="_compute_route_ids"
    )
    route_id = fields.Many2one(
        domain="[('id', 'in', route_ids)]",
        ondelete="restrict",
    )

    @api.depends("product_id", "warehouse_id", "warehouse_id.route_ids", "location_id")
    def _compute_route_ids(self):
        for orderpoint in self:
            wh_routes = orderpoint.warehouse_id._get_all_routes()
            product_routes = self.env["stock.route"]

            if orderpoint.product_id:
                product_routes = orderpoint.product_id.mapped(
                    "route_ids"
                ) | orderpoint.product_id.mapped("categ_id").mapped("total_route_ids")

            # keep the intersection of the rules allowed by the
            # warehouse and the product + product category
            orderpoint.route_ids = product_routes & wh_routes

    def _prepare_procurement_values(self, date=False, group=False):
        res = super()._prepare_procurement_values(date=date, group=group)
        res["route_ids"] = self.route_id
        return res
