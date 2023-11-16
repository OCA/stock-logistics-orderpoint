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

    def _compute_quantities_dict(self, products):
        res = super()._compute_quantities_dict(products)
        if "average_daily_sale" in self.mapped("replenish_method"):
            self._add_recommended_qty_to_qties_dict(res, products)
        return res

    def _add_recommended_qty_to_qties_dict(self, qties_on_locations, products):
        # we add by warehouse the recommended_qty for each product
        wh_ids = {location.warehouse_id.id for location in qties_on_locations}
        recommended_qty = {wh_id: {} for wh_id in wh_ids}
        qties_on_locations["recommended_qty"] = recommended_qty
        product_ids = {p.id for p in products}
        for wh_id in wh_ids:
            not_processed_product_ids = list(product_ids)
            reports = self.env["stock.average.daily.sale"].search(
                [
                    ("product_id", "in", list(product_ids)),
                    ("warehouse_id", "=", wh_id),
                ]
            )
            for report in reports:
                recommended_qty[wh_id][report.product_id] = report.recommended_qty
                not_processed_product_ids.remove(report.product_id.id)
            for product_id in not_processed_product_ids:
                recommended_qty[wh_id][products.browse(product_id)] = 0

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

        recommended_qty = qties_on_locations["recommended_qty"][
            self.location_id.warehouse_id.id
        ][product]
        if not recommended_qty:
            return 0

        # We need to fill the missing quantity between the buffer
        # need value, the existing quantity on destination and the already replenished
        # quantity
        needed_quantity = (
            recommended_qty - virtual_available_on_dest - qty_already_replenished
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
