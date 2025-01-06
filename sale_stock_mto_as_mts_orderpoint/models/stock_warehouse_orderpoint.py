# Copyright 2016-20 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


from odoo import api, fields, models
from odoo.tools import float_compare, float_round


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    procure_recommended_qty = fields.Float(
        string="Procure Recommendation",
        compute="_compute_procure_recommended",
        digits="Product Unit of Measure",
    )
    procure_recommended_date = fields.Date(
        string="Recommended Request Date", compute="_compute_procure_recommended"
    )

    def _get_procure_recommended_qty(self, virtual_qty, op_qtys):
        self.ensure_one()

        target_qty = max(self.product_min_qty, self.product_max_qty)
        qty = target_qty - virtual_qty

        if self.qty_multiple > 0:
            remainder = qty % self.qty_multiple
            if (
                float_compare(
                    remainder, 0.0, precision_rounding=self.product_uom.rounding
                )
                > 0
            ):
                qty += self.qty_multiple - remainder

        if float_compare(qty, 0.0, precision_rounding=self.product_uom.rounding) <= 0:
            return 0.0

        qty -= op_qtys.get(self.id, 0.0)
        qty_rounded = float_round(qty, precision_rounding=self.product_uom.rounding)

        return qty_rounded if qty_rounded > 0 else 0.0

    @api.depends("product_min_qty", "product_id", "qty_multiple")
    def _compute_procure_recommended(self):
        # '_quantity_in_progress' override in 'purchase_stock' method has not
        # been designed to work with NewIds (resulting in KeyError exceptions).
        # To circumvent this, we knowingly skip such records here.
        ops = self.filtered("id")
        # No need to call '_quantity_in_progress()' if there is no orderpoint,
        # this leads to a heavy request done by a call to `read_group` with
        # an empty domain on 'purchase.order.line' in the
        # 'product.product._get_quantity_in_progress()' method.
        op_qtys = ops._quantity_in_progress() if ops else {}

        for op in self:
            if not op.id:
                op.update(
                    {
                        "procure_recommended_qty": False,
                        "procure_recommended_date": False,
                    }
                )
                continue

            virtual_qty = op.with_context(
                location=op.location_id.id
            ).product_id.virtual_available

            qty = 0.0
            if (
                float_compare(
                    virtual_qty,
                    op.product_min_qty,
                    precision_rounding=op.product_uom.rounding or 0.01,
                )
                < 0
            ):
                qty = op._get_procure_recommended_qty(virtual_qty, op_qtys)

            op.update(
                {
                    "procure_recommended_qty": qty,
                    "procure_recommended_date": op.lead_days_date,
                }
            )
