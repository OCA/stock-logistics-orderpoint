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
        self, warehouse: StockWarehouse, days: int, **kwargs
    ) -> dict[Self, list[float]]:
        """Returns the daily demand serie for a given warehouse

        The serie is a zero-filled list of demand values, each corresponding to a day.
        The values are in the product's base unit of measure.
        """
        return {
            prod: prod._zero_fill_demand_serie(demands=demands, days=days, **kwargs)
            for prod, demands in self._get_daily_demand(warehouse, days).items()
        }

    def _zero_fill_demand_serie(
        self,
        *,  # keyword-only arguments
        demands: dict[datetime.date, float | int],
        days: int,
        skip_leading_0s: bool = False,
        **kwargs,
    ) -> list[float]:
        """Returns the serie corresponding to the given params

        :param demands: The daily demands for the product. Represents the qty demanded
            each day.
        :param skip_leading_0s: Whether leading 0s should be skipped in the
            resulting serie.
        :param days: The number of days in the serie, up to today. If param
            ``skip_leading_0s`` is True, this is overridden to be the number of
            days between the first non-null qty date and today.
        :param kwargs: Additional kwargs to pass to customize this method behavior in
            subclasses. Currently supported kwargs:
                - ``today``: the current date; defaults to ``datetime.date.today()``
                - ``start``: the start date of the serie; defaults to ``today - days``

        :return: The serie corresponding to the given params as a list of floats.
        """
        # We have 3 possible cases:
        # 1. the skip-leading-0s feature is not active: we start the serie from the
        #    given ``start`` date for the requested number of ``days``
        # 2. the skip-leading-0s feature is active, but there are no non-null demands
        #    (either we received a dictionary mapping all dates to 0.0, or, most
        #    probably, we just received an empty dictionary): return an empty serie
        # 3. the skip-leading-0s feature is active, and there are non-null demands:
        #    we postpone ``start`` to the first non-null qty's date (if not already a
        #    later date than ``start``), leading to a serie that may contain fewer items
        #    than the requested number of ``days``
        self.ensure_one()
        today: datetime.date = kwargs.get("today") or datetime.date.today()
        # 1st case => compose the serie from ``start`` and go on for ``days`` number of
        # days, even if the resulting serie is made only of 0s
        if not skip_leading_0s:
            start: datetime.date = kwargs.get("start") or (today - timedelta(days=days))
            return [demands.get(start + timedelta(days=i), 0.0) for i in range(days)]
        # 2nd case => early exit with an empty serie
        # NB: ``all()`` returns ``True`` when ``demands`` is an empty dict
        elif all(self.uom_id.is_zero(d) for d in demands.values()):
            return []
        # 3rd case => postpone ``start`` to the first non-null qty's date,
        # recompute the date range with the updated number of days
        start: datetime.date = min(demands)
        days = (today - start).days
        return [demands.get(start + timedelta(days=i), 0.0) for i in range(days)]

    @api.model
    def _get_daily_demand_aggregated_vals(
        self, warehouse: StockWarehouse, days: int, **kwargs
    ) -> dict[Self, dict[str, Any]]:
        """Get the aggregated values of the daily demand per product

        The values are in the product's base unit of measure.

        :param warehouse: The warehouse to get the daily demand for.
        :param days: The number of days to get the daily demand for.
        :return: A dictionary with the aggregated values of the series.
        """
        serie_by_product = self._get_daily_demand_serie(warehouse, days, **kwargs)
        return {
            product: {
                # Returned to ease overrides in subclasses
                "_serie": serie,
                # Values will be written directly to the orderpoint, must be field names
                # 1- ``demand_avg_qty``: average daily demand
                #    NB: check we have at least 1 value, else error is raised:
                #    ``StatisticsError: fmean requires at least one data point``
                "demand_avg_qty": fmean(serie) if len(serie) >= 1 else 0.0,
                # 2- ``demand_std_dev``: standard deviation of daily demand
                #    NB: check we have at least 2 values, else error is raised:
                #    ``StatisticsError: stdev requires at least two data points``
                "demand_std_dev": stdev(serie) if len(serie) >= 2 else 0.0,
            }
            for product, serie in serie_by_product.items()
        }
