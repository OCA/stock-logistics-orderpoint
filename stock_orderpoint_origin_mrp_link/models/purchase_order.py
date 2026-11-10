# Copyright 2021 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _get_mrp_productions(self, **kwargs):
        return (
            super()._get_mrp_productions(**kwargs)
            | self.order_line.source_group_ids.mrp_production_ids
        )

    @api.depends(
        "order_line.source_group_ids.mrp_production_ids",
    )
    def _compute_mrp_production_count(self):
        return super()._compute_mrp_production_count()
