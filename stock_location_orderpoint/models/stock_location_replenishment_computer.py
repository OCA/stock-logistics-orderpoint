# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.osv import expression
from odoo.tools import SQL, float_compare


class StockLocationReplenishmentComputer(models.TransientModel):
    """
    Orderpoint-agnostic replenishment computation engine.

    Instantiated in memory via `new()` — no DB persistence — so it can be
    used for any (location, location_src, strategy) combination without
    requiring an orderpoint record to exist.

    The strategy is injected at instantiation time via _strategy, which
    decouples the computer from any replenish_method resolution logic.
    Adding a new strategy never requires modifying this class.

    Typical usage from an orderpoint::

        computer = orderpoint._get_replenishment_computer()
        procurement_data = computer.compute(products=products, demand_only=False)

    Usage independent of any orderpoint::

        computer = self.env["stock.location.replenishment.computer"].new({
            "location_id": some_location.id,
            "location_src_id": some_src.id,
            "replenish_limit_to_free_qty": True,
            "excluded_location_domain": [...],
        })
        computer._strategy = self.env["stock.location.orderpoint.strategy.fill_up"]
        qty_by_product = computer.compute()
    """

    _name = "stock.location.replenishment.computer"
    _description = "Stock Location Replenishment Computer"

    __slots__ = ["__strategy"]

    location_id = fields.Many2one(
        "stock.location",
        required=True,
        string="Destination Location",
    )
    location_src_id = fields.Many2one(
        "stock.location",
        required=True,
        string="Source Location",
    )
    horizon = fields.Datetime(
        required=True,
        string="Horizon Datetime",
        help="Time horizon to consider for the replenishment. Only moves with a date_deadline"
        "up to this datetime will be considered in the demand computation.",
    )
    replenish_limit_to_free_qty = fields.Boolean(
        default=True,
    )
    excluded_location_domain = fields.Json(
        default=False,
        help="Optional domain to exclude some locations from availability computation. ",
    )
    product_domain = fields.Binary(
        default=[], help="Optional domain to filter products"
    )

    # Strategy instance injected after new() — never persisted.
    # Set explicitly before calling compute():
    #   computer._strategy = orderpoint._strategy_model

    @property
    def _strategy(self):
        if self.__strategy is None:
            raise ValueError(
                "StockLocationReplenishmentComputer._strategy must be set before use"
            )
        return self.__strategy

    @_strategy.setter
    def _strategy(self, value):
        self.__strategy = value

    @property
    def location(self):
        """Return the location_id with the excluded_location_domain applied in context."""
        self.ensure_one()
        return self.location_id.with_context(
            excluded_location_domain=self.excluded_location_domain
        )

    @property
    def location_src(self):
        """Return the location_src_id with the excluded_location_domain applied in context."""
        self.ensure_one()
        return self.location_src_id.with_context(
            excluded_location_domain=self.excluded_location_domain
        )

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def compute(self, products=None, demand_only=False, job_logs=None):
        """
        Compute replenishment quantities for the given products.

        :param products: optional product.product recordset to scope the
            computation. If None, the strategy determines the candidates.
        :param demand_only: if True, stop after demand computation and return
            {product_id: demand_qty} without the availability cap.
            Used by the async path in _run_replenishment so that one job per
            product can be enqueued after a single demand pass, with no
            double calculation.
        :param job_logs: optional list to collect trace messages.

        :return: dict {product_id: demand_qty}       if demand_only=True
                 dict {product_id: qty_to_procure}   if demand_only=False
        """
        self.ensure_one()
        demand_data = self._compute_demand(products)
        if job_logs is not None:
            job_logs.append(
                _(
                    "Demand computed for location %(location)s: %(count)s products.",
                    location=self.location_id.display_name,
                    count=len(demand_data),
                )
            )

        if not demand_data or demand_only:
            return demand_data or {}

        return self._compute_procurement_qty(demand_data, job_logs=job_logs)

    # -------------------------------------------------------------------------
    # Computation pipeline
    # -------------------------------------------------------------------------

    def _compute_demand(self, products=None):
        """
        Compute demand for the given products via the injected strategy.

        :return: dict {product_id: demand_qty}
        """
        self.ensure_one()
        if self.excluded_location_domain:
            if products is not None:
                products = products.with_context(
                    excluded_location_domain=self.excluded_location_domain
                )
        return self._strategy._compute_demand(
            self.location, self.horizon, self.product_domain, products
        )

    def _compute_procurement_qty(self, demand_data, job_logs=None):
        """
        Cap demand to available quantity at the source location.

        The availability check and the qty decision are kept together
        intentionally: splitting them across separate transactions can
        lead to over-replenishment when multiple orderpoints share the
        same source location.

        If replenish_limit_to_free_qty is False, returns demand_data as-is.

        :param demand_data: dict {product_id: demand_qty}
        :return: dict {product_id: qty_to_procure}
        """
        self.ensure_one()
        if not self.replenish_limit_to_free_qty:
            return demand_data

        product_ids = list(demand_data.keys())
        qty_available_data = self._compute_available_quantities(product_ids)

        # prefetch product_ids for uom_id access in float_compare
        self.env["product.product"].browse(qty_available_data.keys())

        result = {
            product_id: qty
            for product_id in demand_data
            if (
                qty := min(
                    demand_data[product_id], qty_available_data.get(product_id, 0)
                )
            )
            and float_compare(
                qty,
                0,
                precision_rounding=self.env["product.product"]
                .browse(product_id)
                .uom_id.rounding,
            )
            == 1
        }
        if job_logs is not None:
            job_logs.append(
                _(
                    "Procurement qty computed for location %(location)s: "
                    "%(count)s products after availability cap.",
                    location=self.location_id.display_name,
                    count=len(result),
                )
            )
        return result

    def _compute_available_quantities(self, product_ids):
        """
        Compute available quantities at location_src for the given products.

        Available qty = stock quant quantities
                      - outgoing confirmed/assigned/partially_available moves

        :param product_ids: list of product IDs to compute availability for
        :return: dict {product_id: qty_available}
        """
        self.ensure_one()
        (
            quant_domain,
            _move_in_domain,
            move_out_domain,
        ) = self.location_src._get_stock_domains()

        if len(product_ids) < 500:
            # IN query too expensive with large product sets — skip when possible
            quant_domain = expression.AND(
                [quant_domain, [("product_id", "in", product_ids)]]
            )
            move_out_domain = expression.AND(
                [move_out_domain, [("product_id", "in", product_ids)]]
            )
        move_out_domain = expression.AND(
            [
                move_out_domain,
                [
                    (
                        "state",
                        "in",
                        ("confirmed", "assigned", "partially_available"),
                    )
                ],
            ]
        )

        # --- STOCK MOVE (OUTGOING) ---
        stock_move_obj = self.env["stock.move"]
        self.env.flush_all()
        stock_move_obj.flush_model(["product_uom_qty"])
        move_query = stock_move_obj._where_calc(move_out_domain)
        stock_move_obj._apply_ir_rules(move_query, "read")
        move_query.groupby = SQL.identifier(stock_move_obj._table, "product_id")
        move_sql = move_query.select(
            SQL.identifier(stock_move_obj._table, "product_id"),
            SQL(
                "- SUM(%s) AS qty",
                SQL.identifier(stock_move_obj._table, "product_uom_qty"),
            ),
        )

        # --- STOCK QUANT ---
        stock_quant_obj = self.env["stock.quant"]
        self.env.flush_all()
        stock_quant_obj.flush_model(["quantity"])
        quant_query = stock_quant_obj._where_calc(quant_domain)
        stock_quant_obj._apply_ir_rules(quant_query, "read")
        quant_query.groupby = SQL.identifier(stock_quant_obj._table, "product_id")
        quant_sql = quant_query.select(
            SQL.identifier(stock_quant_obj._table, "product_id"),
            SQL("SUM(%s) AS qty", SQL.identifier(stock_quant_obj._table, "quantity")),
        )

        # --- UNION ---
        self.env.cr.execute(
            SQL(
                """
            SELECT product_id, SUM(qty) AS qty
            FROM (
                %s
                UNION ALL
                %s
            ) AS combined
            GROUP BY product_id
        """,
                move_sql,
                quant_sql,
            )
        )
        return dict(self.env.cr.fetchall())
