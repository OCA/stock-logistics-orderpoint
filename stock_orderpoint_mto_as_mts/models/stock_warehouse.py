# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models


class StockWarehouse(models.Model):

    _inherit = "stock.warehouse"

    mto_as_mts = fields.Boolean(inverse="_inverse_mto_as_mts")
    archive_orderpoints_mto_removal = fields.Boolean(default=False)

    def _get_locations_for_mto_orderpoints(self):
        self.ensure_one()
        return self.default_orderpoint_location_id or self.lot_stock_id

    def _inverse_mto_as_mts(self):
        for warehouse in self:
            if warehouse.mto_as_mts:
                wh_mto_rules = self.env["stock.rule"].search(
                    [
                        ("route_id.is_mto", "=", True),
                        "|",
                        ("warehouse_id", "=", warehouse.id),
                        ("picking_type_id.warehouse_id", "=", warehouse.id),
                    ]
                )
                if wh_mto_rules:
                    wh_mto_rules.active = False
