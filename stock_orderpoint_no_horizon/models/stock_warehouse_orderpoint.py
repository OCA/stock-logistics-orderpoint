# Copyright 2023 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2025 Camptocamp SA

from odoo import models


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _get_product_context(self, visibility_days=0):
        ctx = super()._get_product_context(visibility_days=visibility_days)
        if "to_date" in ctx:
            del ctx["to_date"]
        return ctx
