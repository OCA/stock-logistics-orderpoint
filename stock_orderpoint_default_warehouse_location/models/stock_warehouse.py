# Copyright 2024 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    orderpoint_loc_id = fields.Many2one(
        "stock.location", "Orderpoint Location", check_company=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for wh in res:
            wh.orderpoint_loc_id = wh.lot_stock_id
        return res
