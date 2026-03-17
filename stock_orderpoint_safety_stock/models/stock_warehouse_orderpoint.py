# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import math

from odoo import api, fields, models
from odoo.tools.constants import PREFETCH_MAX


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    safety_stock_method = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("csl", "Cycle Service Level"),
        ],
        default="manual",
        help=(
            "The method to use to set the product's min and max quantities.\n"
            "* Manual: The product's min and max quantities are set manually.\n"
            "* Cycle Service Level: The product's min and max quantities are computed "
            "based on the target cycle service level and the growth factor.\n"
        ),
    )
    cycle_service_level_id = fields.Many2one(
        "stock.cycle.service.level",
        string="Cycle Service Level",
        ondelete="restrict",
    )
    csl = fields.Float(
        string="Cycle Service Level Target",
        related="cycle_service_level_id.csl",
    )
    z_score = fields.Float(
        related="cycle_service_level_id.z_score",
    )
    growth_factor = fields.Float(
        digits=(2, 2),
        default=0.0,
        help=(
            "A multiplier to apply to the safety stock and the resulting min and max "
            "quantities. Used to account for expected growth or decrease in demand."
        ),
    )
    cycle_days = fields.Integer(
        help=(
            "The desired number of days between orders.\n"
            "Used to size the gap between the min and max quantities, "
            "to cover the expected demand during the desired reordering cycle.\n\n"
            "product_max_qty = product_min_qty + (demand_avg_qty * cycle_days)"
        ),
    )
    demand_history_days = fields.Integer(
        string="Demand History Days",
        related="company_id.demand_history_days",
    )
    demand_avg_qty = fields.Float(
        string="Average Daily Demand",
        compute="_compute_daily_demand",
        digits="Product Unit",
        help="The average daily outgoing quantity on this warehouse.",
    )
    demand_std_dev = fields.Float(
        string="Standard Deviation of Daily Demand",
        compute="_compute_daily_demand",
        digits="Product Unit",
        help="The standard deviation of the daily outgoing quantity on this warehouse.",
    )
    demand_lt_std_dev = fields.Float(
        string="Standard Deviation of Daily Demand over Lead Time",
        compute="_compute_demand_lt_std_dev",
        digits="Product Unit",
        help=(
            "The standard deviation of the daily outgoing quantity on this warehouse "
            "over the lead time."
        ),
    )
    safety_stock = fields.Float(
        compute="_compute_safety_stock",
        digits="Product Unit",
        help=(
            "The safety stock is the amount of stock to keep on this warehouse to "
            "cover for the variability in demand during the lead time.\n"
            "It is computed as the product of the standard deviation of the daily "
            "outgoing quantity over the lead time, the z-score (statistical factor "
            "derived from the target cycle service level) and the growth factor.\n\n"
            "safety_stock = demand_lt_std_dev * z_score * (1.0 + growth_factor)"
        ),
    )
    safety_stock_update_date = fields.Datetime(
        string="Last modification date of Min and Max quantities from Safety Stock",
        readonly=True,
    )

    @api.depends(
        "safety_stock_method",
        "demand_history_days",
        "warehouse_id",
        "product_id",
        "product_id.stock_move_ids",
    )
    def _compute_daily_demand(self):
        """Compute the Average Daily Demand and its Standard Deviation."""
        # Clear existing values
        self.demand_avg_qty = 0.0
        self.demand_std_dev = 0.0
        # Group by warehouse and demand history days to batch read groups of stock moves
        grouped = self.grouped(lambda rec: (rec.warehouse_id, rec.demand_history_days))
        for (warehouse, days), orderpoints in grouped.items():
            products = orderpoints.product_id
            aggregated_vals_by_product = products._get_daily_demand_aggregated_vals(
                warehouse=warehouse,
                days=days,
            )
            for orderpoint in orderpoints:
                vals = aggregated_vals_by_product.get(orderpoint.product_id, {})
                orderpoint.update(
                    {
                        # The value is expressed in the product's base unit of measure.
                        # The orderpoint's product_uom is normally the same, but in case
                        # another module modifies it, we make sure to convert it.
                        fname: orderpoint.product_id.uom_id._compute_quantity(
                            value,
                            orderpoint.product_id.uom_id,
                            round=False,
                        )
                        for fname, value in vals.items()
                        # The :meth:`_get_daily_demand_aggregated_vals` returns a
                        # `_serie` key to ease overrides in subclasses, which must
                        # not be written to the orderpoint.
                        if fname in self._fields
                    }
                )

    @api.depends("demand_std_dev", "lead_days")
    def _compute_demand_lt_std_dev(self):
        for rec in self:
            rec.demand_lt_std_dev = rec.demand_std_dev * math.sqrt(rec.lead_days)

    @api.depends(
        "product_uom",
        "safety_stock_method",
        "demand_lt_std_dev",
        "z_score",
        "growth_factor",
    )
    def _compute_safety_stock(self):
        for rec in self:
            if not rec.product_id or not rec.product_uom:
                rec.safety_stock = 0.0
                continue
            rec.safety_stock = rec.product_uom.round(
                rec.demand_lt_std_dev * rec.z_score * (1.0 + rec.growth_factor)
            )

    def _get_min_max_quantities_from_safety_stock(self) -> tuple[float, float]:
        """Get the min and max quantities to apply derived from the safety stock

        The safety stock is a buffer to cover for variability in demand.
        The min quantity covers for the demand during the lead time.
        The maximum quantity covers for the demand during the desired reordering cycle.
        """
        self.ensure_one()
        # We adjust the average daily demand with the growth factor to account for
        # expected growth or decrease in demand.
        demand_avg_qty_adjusted = self.demand_avg_qty * (1.0 + self.growth_factor)
        # The minimum covers for the demand during the lead time (+ safety stock)
        min_qty = self.product_uom.round(
            self.safety_stock + (demand_avg_qty_adjusted * self.lead_days)
        )
        # The maximum quantity covers for the demand during the desired reordering cycle
        max_qty = self.product_uom.round(
            min_qty + (demand_avg_qty_adjusted * self.cycle_days)
        )
        return min_qty, max_qty

    def _apply_safety_stock(self):
        """Apply the safety stock to the orderpoint min and max quantities"""
        if not self.product_id or not self.product_uom:
            return
        to_apply = self.filtered(lambda rec: rec.safety_stock_method != "manual")
        to_apply.safety_stock_update_date = fields.Datetime.now()
        uom_unit = self.env.ref("uom.product_uom_unit")
        for rec in to_apply:
            min_qty, max_qty = rec._get_min_max_quantities_from_safety_stock()
            # If the product UoM has a common reference with the unit UoM,
            # we round the quantities to the nearest integer, units can't be fractional.
            if rec.product_uom._has_common_reference(uom_unit):
                min_qty = math.ceil(min_qty)
                max_qty = math.ceil(max_qty)
            rec.product_min_qty = min_qty
            rec.product_max_qty = max_qty

    def action_apply_safety_stock(self):
        """Apply the safety stock to the orderpoint min and max quantities"""
        self._apply_safety_stock()
        return True

    @api.onchange(
        "product_id",
        "location_id",
        "safety_stock_method",
        "cycle_service_level_id",
        "growth_factor",
        "cycle_days",
    )
    def _onchange_safety_stock_method_apply(self):
        """Onchange: safety stock method or cycle service level

        Immediately apply the safety stock to the orderpoint min and max quantities.
        """
        self._apply_safety_stock()

    @api.model
    def _cron_recompute_safety_stock(self, batch_size: int | None = PREFETCH_MAX):
        """Scheduled action: Recompute the safety stock for all orderpoints"""
        domain = [
            ("safety_stock_method", "!=", "manual"),
            ("safety_stock_update_date", "<", "today"),
        ]
        records = self.search(domain, order="id", limit=batch_size)
        records._apply_safety_stock()
        remaining = self.search_count(domain)
        self.env["ir.cron"]._commit_progress(
            processed=len(records),
            remaining=remaining,
        )
