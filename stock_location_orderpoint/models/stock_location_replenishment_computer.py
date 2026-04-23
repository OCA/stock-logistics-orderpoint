# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.osv import expression
from odoo.tools import float_compare


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
    replenish_limit_to_free_qty = fields.Boolean(
        default=True,
    )
    excluded_location_domain = fields.Json(
        default=False,
        help="Optional domain to exclude some locations from availability computation. ",
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
        location = self.location_id
        if self.excluded_location_domain:
            if products is not None:
                products = products.with_context(
                    excluded_location_domain=self.excluded_location_domain
                )
            location = location.with_context(
                excluded_location_domain=self.excluded_location_domain
            )
        return self._strategy._compute_demand(location, products)

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
        location_model = self.env["stock.location"]
        if self.excluded_location_domain:
            location_model = location_model.with_context(
                excluded_location_domain=self.excluded_location_domain
            )

        (
            quant_domain,
            _move_in_domain,
            move_out_domain,
        ) = location_model._get_stock_domains(self.location_src_id.id)

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
        stock_move_obj._flush_search(move_out_domain)
        stock_move_obj.flush_model(["product_uom_qty"])
        move_query = stock_move_obj._where_calc(move_out_domain)
        stock_move_obj._apply_ir_rules(move_query, "read")
        move_tables, move_where, move_params = move_query.get_sql()
        move_sql = f"""
            SELECT
                {stock_move_obj._table}.product_id,
                - SUM({stock_move_obj._table}.product_uom_qty) AS qty
            FROM {move_tables}
            WHERE {move_where}
            GROUP BY {stock_move_obj._table}.product_id
        """

        # --- STOCK QUANT ---
        stock_quant_obj = self.env["stock.quant"]
        stock_quant_obj._flush_search(quant_domain)
        stock_quant_obj.flush_model(["quantity"])
        quant_query = stock_quant_obj._where_calc(quant_domain)
        stock_quant_obj._apply_ir_rules(quant_query, "read")
        quant_tables, quant_where, quant_params = quant_query.get_sql()
        quant_sql = f"""
            SELECT
                {stock_quant_obj._table}.product_id,
                SUM({stock_quant_obj._table}.quantity) AS qty
            FROM {quant_tables}
            WHERE {quant_where}
            GROUP BY {stock_quant_obj._table}.product_id
        """

        # --- UNION ---
        final_sql = f"""
            SELECT product_id, SUM(qty) AS qty
            FROM (
                {move_sql}
                UNION ALL
                {quant_sql}
            ) AS combined
            GROUP BY product_id
        """
        self.env.cr.execute(final_sql, move_params + quant_params)
        return dict(self.env.cr.fetchall())
