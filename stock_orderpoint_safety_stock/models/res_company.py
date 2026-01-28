# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    demand_history_days = fields.Integer(
        default=365,
        help="The number of days in the past to use to compute the safety stock.",
    )
