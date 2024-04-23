# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockWarehouse(models.Model):

    _inherit = "stock.warehouse"

    default_orderpoint_location_id = fields.Many2one(
        comodel_name="stock.location",
        help="Choose here a stock location that will be used as default one "
        "for new orderpoints. Either the default behavior will be used and "
        " will choose the 'Location Stock'.",
    )
