# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import datetime
from datetime import timedelta
from statistics import fmean, stdev
from typing import Any

from odoo import api, models
from odoo.api import Self
from odoo.fields import Domain

from odoo.addons.stock.models.stock_warehouse import StockWarehouse


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _get_daily_demand_moves_location_domain(
        self, warehouse: StockWarehouse
    ) -> Domain:
        """Returns the location domain leaf for the daily demand moves of a warehouse

        This is strongly based in:
        https://github.com/odoo/odoo/blob/d2ea875a/addons/purchase_stock/models/product.py#L136-L157

        We include moves:
            - going to customer locations or used in production
            - going to other warehouses (eg. central warehouse dispatching to stores)

        We exclude:
            - returns: in demand estimation, they come back on hand
        """
        return Domain.AND(
            [
                Domain("location_id.warehouse_id", "=", warehouse.id),
                # Includes moves going to the customer or production locations
                Domain.OR(
                    [
                        [("location_dest_id.warehouse_id", "!=", warehouse.id)],
                        [("location_final_id.warehouse_id", "!=", warehouse.id)],
                    ]
                ),
                # Exclude scrap/inventory adjustments
                Domain("location_dest_id.usage", "!=", "inventory"),
            ]
        )

    @api.model
    def _get_daily_demand_moves_domain(
        self, warehouse: StockWarehouse, days: int
    ) -> Domain:
        """Returns the domain for the daily demand moves of a warehouse"""
        # For a demand computation, confirmed and assigned moves are counted
        moves_states = ["assigned", "confirmed", "partially_available", "done"]
        moves_domain = Domain(
            [
                ("product_id", "in", self.ids),
                ("date", ">=", f"today -{days}d"),
                ("date", "<", "today"),
                ("state", "in", moves_states),
                ("product_qty", ">", 0),
            ]
        )
        return Domain.AND(
            [
                moves_domain,
                self._get_daily_demand_moves_location_domain(warehouse),
            ]
        )

    @api.model
    def _get_daily_demand(
        self, warehouse: StockWarehouse, days: int
    ) -> dict[Self, dict[datetime.date, float]]:
        """Returns the daily demand by date for a given warehouse

        The values are in the product's base unit of measure.
        """
        moves_domain = self._get_daily_demand_moves_domain(warehouse, days)
        groups = self.env["stock.move"]._read_group(
            moves_domain,
            groupby=["product_id", "date:day"],
            aggregates=["product_qty:sum"],
        )
        res = {product: {} for product in self}
        for product, date, demand in groups:
            res[product][date.date()] = demand
        return res

    @api.model
    def _get_daily_demand_serie(
        self, warehouse: StockWarehouse, days: int
    ) -> dict[Self, list[float]]:
        """Returns the daily demand serie for a given warehouse

        The serie is a zero-filled list of demand values, each corresponding to a day.
        The values are in the product's base unit of measure.
        """
        daily_demand_by_product = self._get_daily_demand(warehouse, days)
        today = datetime.date.today()
        fill_from = today - timedelta(days=days)
        fill_to = today
        serie_length = (fill_to - fill_from).days
        return {
            product: [
                daily_demand.get(fill_from + timedelta(days=i), 0.0)
                for i in range(serie_length)
            ]
            for product, daily_demand in daily_demand_by_product.items()
        }

    @api.model
    def _get_daily_demand_aggregated_vals(
        self, warehouse: StockWarehouse, days: int
    ) -> dict[str, Any]:
        """Get the aggregated values of the daily demand per product

        The values are in the product's base unit of measure.

        :param warehouse: The warehouse to get the daily demand for.
        :param days: The number of days to get the daily demand for.
        :return: A dictionary with the aggregated values of the series.
        """
        serie_by_product = self._get_daily_demand_serie(warehouse, days)
        return {
            product: {
                # Returned to ease overrides in subclasses
                "_serie": serie,
                # Values will be written directly to the orderpoint, must be field names
                "demand_avg_qty": fmean(serie),  # Average daily demand
                "demand_std_dev": stdev(serie),  # Standard deviation of daily demand
            }
            for product, serie in serie_by_product.items()
        }
