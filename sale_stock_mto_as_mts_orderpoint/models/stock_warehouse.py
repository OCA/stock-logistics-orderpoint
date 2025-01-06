# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    mto_as_mts = fields.Boolean(inverse="_inverse_mto_as_mts")

    def _get_locations_for_mto_orderpoints(self):
        self.fetch(["lot_stock_id"])
        return self.mapped("lot_stock_id")

    def _inverse_mto_as_mts(self):
        mto_route = self.env.ref("stock.route_warehouse0_mto", raise_if_not_found=False)
        if not mto_route:
            return

        warehouses_with_mto = self.filtered("mto_as_mts")
        if not warehouses_with_mto:
            return

        domain = [
            ("route_id", "=", mto_route.id),
            "|",
            ("warehouse_id", "in", warehouses_with_mto.ids),
            ("picking_type_id.warehouse_id", "in", warehouses_with_mto.ids),
        ]

        wh_mto_rules = self.env["stock.rule"].search(domain)
        if wh_mto_rules:
            wh_mto_rules.write({"active": False})
