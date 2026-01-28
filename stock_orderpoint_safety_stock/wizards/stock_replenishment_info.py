# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import api, fields, models

CYCLE_PERIODS = {
    "daily": 1,
    "weekly": 7,
    "bi-weekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "semi-annually": 180,
    "yearly": 365,
}


class StockReplenishmentInfo(models.TransientModel):
    _inherit = "stock.replenishment.info"

    safety_stock_method = fields.Selection(
        related="orderpoint_id.safety_stock_method",
        readonly=False,
    )
    cycle_service_level_id = fields.Many2one(
        related="orderpoint_id.cycle_service_level_id",
        readonly=False,
    )
    z_score = fields.Float(
        related="orderpoint_id.z_score",
        depends=["orderpoint_id.cycle_service_level_id"],
    )
    growth_factor = fields.Float(
        related="orderpoint_id.growth_factor",
        readonly=False,
    )
    cycle_days = fields.Integer(
        related="orderpoint_id.cycle_days",
        readonly=False,
    )

    # Computed demand fields
    demand_history_days = fields.Integer(related="orderpoint_id.demand_history_days")
    demand_avg_qty = fields.Float(related="orderpoint_id.demand_avg_qty")
    demand_std_dev = fields.Float(related="orderpoint_id.demand_std_dev")
    demand_lt_std_dev = fields.Float(related="orderpoint_id.demand_lt_std_dev")
    safety_stock = fields.Float(related="orderpoint_id.safety_stock")

    @api.onchange(
        "safety_stock_method",
        "cycle_service_level_id",
        "growth_factor",
        "cycle_days",
    )
    def _onchange_safety_stock_method_apply(self):
        """Onchange: safety stock method or cycle service level

        Recompute the min and max quantities based on the safety stock.
        """
        virtual_orderpoint = self.orderpoint_id.new(origin=self.orderpoint_id)
        virtual_orderpoint.update(
            {
                "safety_stock_method": self.safety_stock_method,
                "cycle_service_level_id": self.cycle_service_level_id,
                "growth_factor": self.growth_factor,
                "cycle_days": self.cycle_days,
            }
        )
        virtual_orderpoint._apply_safety_stock()
        self.update(
            {
                "safety_stock": virtual_orderpoint.safety_stock,
                "product_min_qty": virtual_orderpoint.product_min_qty,
                "product_max_qty": virtual_orderpoint.product_max_qty,
            }
        )

    @api.depends("safety_stock_method", "safety_stock")
    def _compute_json_replenishment_graph(self):  # pylint: disable=missing-return
        # OVERRIDE: Completely override the graph data in case of safety stock
        records = self.filtered(lambda rec: rec.safety_stock_method != "manual")
        others = self - records
        super(StockReplenishmentInfo, others)._compute_json_replenishment_graph()
        for rec in records:
            if (
                not rec.product_id
                or not rec.orderpoint_id.location_id
                or not rec.cycle_service_level_id
            ):
                continue
            average_stock = rec.product_min_qty + (
                (rec.product_max_qty - rec.product_min_qty) / 2
            )
            ordering_period, graph_data = rec._prepare_graph_data(
                daily_demand=rec.demand_avg_qty * (1 + rec.growth_factor)
            )
            rec.json_replenishment_graph = json.dumps(
                {
                    "safety_stock_method": rec.safety_stock_method,
                    "product_uom_name": rec.product_uom_name,
                    "product_max_qty": rec.product_max_qty,
                    "product_min_qty": rec.product_min_qty,
                    "qty_on_hand": rec.orderpoint_id.qty_on_hand,
                    "lead_time": rec.orderpoint_id.lead_days,
                    "daily_demand": rec.demand_avg_qty,
                    "safety_stock": rec.safety_stock,
                    "average_stock": rec.orderpoint_id.product_uom.round(average_stock),
                    "std_dev": rec.demand_std_dev,
                    "demand_history_days": rec.demand_history_days,
                    "ordering_period": fields.Float.round(
                        ordering_period, precision_rounding=1
                    ),
                    "x_axis_vals": graph_data["x_axis_vals"],
                    "max_line_vals": graph_data["max_line_vals"],
                    "min_line_vals": graph_data["min_line_vals"],
                    "curve_line_vals": graph_data["curve_line_vals"],
                    "safety_stock_line_vals": graph_data["safety_stock_line_vals"],
                }
            )

    def _prepare_graph_data(self, daily_demand=0):
        # OVERRIDE to add the safety stock line to the graph
        ordering_period, graph_data = super()._prepare_graph_data(
            daily_demand=daily_demand
        )
        if self.safety_stock_method != "manual":
            graph_data["safety_stock_line_vals"] = [
                {
                    "x": item["x"],
                    "y": self.safety_stock,
                }
                for item in graph_data["max_line_vals"]
            ]
        return ordering_period, graph_data
