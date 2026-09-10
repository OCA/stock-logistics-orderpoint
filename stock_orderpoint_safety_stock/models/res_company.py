# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    demand_history_days = fields.Integer(
        default=365,
        help="The number of days in the past to use to compute the safety stock.",
    )
    demand_serie_skip_leading_0s = fields.Boolean(
        help=(
            "If checked, all orderpoints linked to one of this company's warehouses"
            " will compute the 'Average Daily Demand' and 'Standard Deviation"
            " of Daily Demand' fields values starting from the day of the product's"
            " earliest moved quantity within the selected timerange; else, they will be"
            " computed from the beginning of the timerange."
        ),
    )
