# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import ast
import math

from pyerf import erfinv

from odoo import api, fields, models


def norm_ppf(p: float) -> float:
    """Percent point function (inverse CDF) of the standard normal distribution.

    This method is equal to the `norm.ppf` function from the `scipy.stats` library,
    except it requires a lighter dependency: `pyerf`.

    :param p: The probability.
    :return: The z-score.
    :raises ValueError: If the probability is not between 0 and 1.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("The probability must be between 0 and 1")
    return math.sqrt(2.0) * erfinv(2.0 * p - 1.0)


class StockCycleServiceLevel(models.Model):
    _name = "stock.cycle.service.level"
    _description = "Cycle Service Level"
    _rec_name = "display_name"
    _order = "csl desc"

    csl = fields.Float(
        string="Cycle Service Level",
        digits=(2, 2),
        help=(
            "The probability that demand during the replenishment lead time is fully "
            "covered without a stockout.\n"
            "This value defines how reliable the stock should be during each "
            "replenishment cycle. A higher target increases safety stock to reduce the "
            "risk of stockouts; a lower target reduces inventory at the cost of more "
            "frequent shortages.\n"
            "Typical values range from 0.90 to 0.99 (e.g., 0.95 = 95% of cycles "
            "without stockouts)."
        ),
    )
    z_score = fields.Float(
        string="Z-Score",
        digits=(16, 4),
        compute="_compute_z_score",
        store=True,
        help=(
            "Statistical factor derived from the target cycle service level.\n\n"
            "The z-score represents how many standard deviations of demand variability "
            "are covered by the safety stock.\n"
            "A higher z-score corresponds to a higher service level and results in "
            "more safety stock."
        ),
    )
    orderpoint_ids = fields.One2many(
        "stock.warehouse.orderpoint",
        "cycle_service_level_id",
        string="Orderpoints",
    )
    orderpoint_count = fields.Integer(
        string="Orderpoints Count",
        compute="_compute_orderpoint_count",
    )

    _check_csl_range = models.Constraint(
        "CHECK(csl >= 0 AND csl < 1)",
        "The cycle service level must be between 0 and 1, typically 0.90...0.99.",
    )
    _check_csl_unique = models.Constraint(
        "UNIQUE(csl)",
        "There's already a cycle service level with this value.",
    )

    @api.depends("csl")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.csl:.2%}"

    @api.depends("csl")
    def _compute_z_score(self):
        for record in self:
            record.z_score = norm_ppf(record.csl) if 0.0 < record.csl < 1.0 else 0.0

    @api.depends("orderpoint_ids")
    def _compute_orderpoint_count(self):
        groups = self.env["stock.warehouse.orderpoint"]._read_group(
            [("cycle_service_level_id", "in", self.ids)],
            ["cycle_service_level_id"],
            ["cycle_service_level_id:count"],
        )
        data = {group[0].id: group[1] for group in groups}
        for record in self:
            record.orderpoint_count = data.get(record.id, 0)

    def action_open_orderpoints(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_orderpoint_replenish"
        )
        action["domain"] = [("cycle_service_level_id", "in", self.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action["context"]) or {},
            default_safety_stock_method="csl",
        )
        if len(self) == 1:
            action["context"]["default_cycle_service_level_id"] = self.id
        return action
