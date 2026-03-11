# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import csv
import datetime
import math
from collections.abc import Sequence
from statistics import fmean, stdev

from odoo import fields
from odoo.tests import TransactionCase
from odoo.tools import file_open

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT
from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.stock.models.stock_move import StockMove


class OrderpointSafetyStockCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.today = fields.Date.today()
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
            }
        )
        # Quick reference to common CSLs
        csl_xmlid_prefix = "stock_orderpoint_safety_stock.stock_cycle_service_level"
        cls.csl_90 = cls.env.ref(f"{csl_xmlid_prefix}_90")
        cls.csl_95 = cls.env.ref(f"{csl_xmlid_prefix}_95")
        cls.csl_97 = cls.env.ref(f"{csl_xmlid_prefix}_97")
        cls.csl_99 = cls.env.ref(f"{csl_xmlid_prefix}_99")
        # Create an orderpoint for the product
        cls.orderpoint = cls.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": cls.product.id,
                "warehouse_id": cls.warehouse.id,
                "safety_stock_method": "csl",
                "cycle_service_level_id": cls.csl_95.id,
            }
        )

    @classmethod
    def _create_moves_from_serie(
        cls,
        product: ProductProduct,
        serie: Sequence[tuple[datetime.date, float]],
        vals: dict | None = None,
    ) -> StockMove:
        move_vals = []
        for date, qty in serie:
            if qty > 0:
                location_id = cls.warehouse.lot_stock_id
                location_dest_id = cls.customer_location
            else:
                location_id = cls.customer_location
                location_dest_id = cls.warehouse.lot_stock_id
            move_vals.append(
                {
                    "product_id": product.id,
                    "product_uom_qty": abs(qty),
                    "date": fields.Date.to_date(date),
                    "location_id": location_id.id,
                    "location_dest_id": location_dest_id.id,
                    "company_id": cls.warehouse.company_id.id,
                    # Already done moves
                    "state": "done",
                    "quantity": abs(qty),
                    # Additional values
                    **(vals or {}),
                }
            )
        return cls.env["stock.move"].create(move_vals)

    @classmethod
    def _load_serie_from_csv(cls, path: str) -> Sequence[tuple[datetime.date, float]]:
        """Load a series of dates and quantities from a CSV file.

        :param path: The path to the CSV file, see :meth:`odoo.tools.file_open`.
        :return: A sequence of tuples with the dates and quantities.
        """
        with file_open(path) as f:
            reader = csv.reader(f)
            return [(fields.Date.to_date(date), float(qty)) for (date, qty) in reader]

    @classmethod
    def _compute_values(
        self,
        serie: list[float],
        z_score: float = 1.6449,
        growth: float = 0.0,
        lead_days: int = 1,
        cycle_days: int = 0,
        round_min_max_to_unit: bool = False,
    ) -> dict[str, float]:
        """Compute the expected values for the provided serie, using a simple math.

        When round_min_max_to_unit is True, product_min_qty and product_max_qty
        are ceiled to integers (matching the model behavior for unit UoM).
        """
        avg_qty = round(fmean(serie), 2)
        std_dev = round(stdev(serie), 2)
        std_dev_lt = std_dev * math.sqrt(lead_days)
        growth_ratio = 1 + growth
        safety_stock = round(std_dev_lt * z_score * growth_ratio, 2)
        min_qty = round(safety_stock + (avg_qty * lead_days * growth_ratio), 2)
        max_qty = round(min_qty + (avg_qty * cycle_days * growth_ratio), 2)
        if round_min_max_to_unit:
            min_qty = math.ceil(min_qty)
            max_qty = math.ceil(max_qty)
        return {
            "demand_avg_qty": avg_qty,
            "demand_std_dev": std_dev,
            "demand_lt_std_dev": std_dev_lt,
            "safety_stock": safety_stock,
            "product_min_qty": min_qty,
            "product_max_qty": max_qty,
        }

    @classmethod
    def _get_orderpoint_serie(cls, orderpoint) -> list[float]:
        """Get the filled serie of the orderpoint using real moves data

        Returns a zero-filled serie of the demand history.
        """
        return cls.orderpoint.product_id._get_daily_demand_serie(
            orderpoint.warehouse_id,
            orderpoint.demand_history_days,
        )[orderpoint.product_id]
