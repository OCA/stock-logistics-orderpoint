# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockRoute(models.Model):
    _inherit = "stock.route"

    orderpoint_source_limit_available = fields.Boolean(
        help="Check this to limit the movement creation for orderpoints "
        "using this route to quantity available at source location."
    )
