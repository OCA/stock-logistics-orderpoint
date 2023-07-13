# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models
from odoo.tools import float_compare


class StockLocationOrderpoint(models.Model):

    _inherit = "stock.location.orderpoint"

    replenish_method = fields.Selection(
        selection_add=[("average_daily_sale", "Average Daily Sale")],
        ondelete={"average_daily_sale": "cascade"},
    )

    def _get_qty_to_replenish(
        self, product, qties_on_locations, qty_already_replenished=0
    ):
        """
        Returns a qty to replenish for a given orderpoint and product
        """
        self.ensure_one()
        product.ensure_one()

        if self.replenish_method == "average_daily_sale":
            return self._get_qty_to_replenish_average_daily_sale(
                product, qties_on_locations, qty_already_replenished
            )
        return super()._get_qty_to_replenish(
            product=product,
            qties_on_locations=qties_on_locations,
            qty_already_replenished=qty_already_replenished,
        )

    def _get_qty_to_replenish_average_daily_sale(
        self, product, qties_on_locations, qty_already_replenished=0
    ):
        """
        The aim here is to base our needed quantity on average daily sales
        computations (see stock_average_daily_sale module).
        This is a buffer computed in order to prevent missing quantities
        on previsional outgoing quantities (as it can exist difficulties to
        replenish (time, ...)).
        """
        if not self.location_src_id:
            return 0
        qties_on_dest = qties_on_locations[self.location_id][product]
        virtual_available_on_dest = qties_on_dest["virtual_available"]
        qties_on_src = qties_on_locations[self.location_src_id][product]
        virtual_available_on_src = (
            qties_on_src["virtual_available"] - qties_on_src["incoming_qty"]
        )

        reports = self.env["stock.average.daily.sale"].search(
            [
                ("product_id", "=", product.id),
                ("warehouse_id", "=", self.location_id.warehouse_id.id),
            ]
        )
        if not reports:
            return 0

        # We need to fill the missing quantity between the buffer
        # need value, the existing quantity on destination and the already replenished
        # quantity
        needed_quantity = (
            reports.recommended_qty
            - virtual_available_on_dest
            - qty_already_replenished
        )
        qty_to_replenish = min(virtual_available_on_src, needed_quantity)

        if (
            float_compare(
                qty_to_replenish, 0, precision_rounding=product.uom_id.rounding
            )
            > 0
        ):
            return qty_to_replenish
        return 0
