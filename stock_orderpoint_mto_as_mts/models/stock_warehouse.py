# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models


class StockWarehouse(models.Model):

    _inherit = "stock.warehouse"

    mto_as_mts = fields.Boolean(default=False)
    archive_orderpoints_mto_removal = fields.Boolean(default=False)

    def _get_locations_for_mto_orderpoints(self):
        self.ensure_one()
        return self.default_orderpoint_location_id or self.lot_stock_id
