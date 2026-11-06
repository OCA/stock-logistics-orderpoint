# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.osv import expression


class StockLocationOrderpointStrategyAverageDailyUsage(models.AbstractModel):
    _inherit = "stock.location.orderpoint.strategy"
    _name = "stock.location.orderpoint.strategy.average_daily_usage"
    _description = (
        "Stock location orderpoint strategy: "
        "replenish according to the past average daily usage"
    )

    @api.model
    def _get_candidate_products(self, location, horizon, product_domain, products=None):
        """
        In the average daily usage strategy, if the orderpoint is triggered without
        specifying products, we don't return products. Indeed, the candidate products will be
        determined at the demand computation step, based on the products for which we have an
        average daily usage at the destination location of the orderpoint. If no product is
        passed to the demand method, it means that the orderpoint has been triggered for
        all products.

        :param location: stock.location record
        :param horizon: datetime, time horizon to consider for the replenishment
        :param product_domain: domain to filter products
        :return: product.product recordset
        """
        if products:
            if product_domain:
                products = products.filtered_domain(product_domain)
        elif product_domain:
            products = self.env["product.product"].search(product_domain)
        return products

    @api.model
    def _compute_demand(
        self, location, horizon, product_domain, products
    ) -> dict[int, float]:
        """
        Compute demand for the given products according to the average daily usage strategy.
        The demand is computed based on the past average daily usage at the destination location
        of the orderpoint minus the quantity still available at the location,
        plus the quantity already leaving the location.

        :param location: stock.location record
        :param horizon: datetime, time horizon to consider for the replenishment
        :param products: product.product recordset
        """
        # --- STOCK AVERAGE DAILY USAGE ---

        stock_avg_daily_usage_obj = self.env["stock.average.daily.usage"]
        self.env.cr.execute(
            f"SELECT relispopulated FROM pg_class WHERE relname = '{stock_avg_daily_usage_obj._table}';"
        )
        if not (self.env.cr.fetchone()[0]):
            return {}

        stock_location_obj = self.env["stock.location"]
        location_domain = location._get_daily_usage_products_location_domain(
            location.id
        )
        stock_location_obj._flush_search(location_domain)
        loc_query = stock_location_obj._where_calc(location_domain)
        stock_location_obj._apply_ir_rules(loc_query, "read")

        domain = []
        if products is not None:
            domain.append(("product_id", "in", products.ids))

        stock_avg_daily_usage_obj._flush_search(domain)
        adu_query = stock_avg_daily_usage_obj._where_calc(domain)
        stock_avg_daily_usage_obj._apply_ir_rules(adu_query, "read")

        # join location
        loc_alias = adu_query.join(
            stock_avg_daily_usage_obj._table,
            "location_id",
            stock_location_obj._table,
            "id",
            "locations",
        )
        expression.expression(location_domain, stock_location_obj, loc_alias, adu_query)

        # Retrieve candidate ADU records to compute recommended_qty via the ORM
        adu_from, adu_where, adu_params = adu_query.get_sql()
        adu_fetch_sql = f"""
            SELECT {stock_avg_daily_usage_obj._table}.id
            FROM {adu_from}
            WHERE {adu_where}
        """
        self.env.cr.execute(adu_fetch_sql, adu_params)
        adu_ids = [row[0] for row in self.env.cr.fetchall()]
        if not adu_ids:
            return {}

        adu_records = stock_avg_daily_usage_obj.browse(adu_ids)

        # Aggregate recommended quantities per product
        product_recommended_qtys = {}
        for rec in adu_records:
            if rec.recommended_qty > 0.0:
                product_recommended_qtys[rec.product_id.id] = (
                    product_recommended_qtys.get(rec.product_id.id, 0.0)
                    + rec.recommended_qty
                )

        if not product_recommended_qtys:
            return {}

        # Build dynamic VALUES clause for the avg_daily_usage CTE
        adu_placeholders = ", ".join(
            ["(%s::integer, %s::numeric)"] * len(product_recommended_qtys)
        )
        adu_sql = f"""
            SELECT * FROM (VALUES {adu_placeholders}) AS t(product_id, qty)
        """
        adu_params = []
        for product_id, product_qty in product_recommended_qtys.items():
            adu_params.extend([product_id, product_qty])

        # --- STOCK MOVE (OUTGOING) with condition on products ---
        # --- for which we have an average daily usage at the location ---

        outgoing_moves_domain = location._get_consuming_moves_domain()
        outgoing_moves_domain = expression.AND(
            [outgoing_moves_domain, [("date", "<=", horizon)]]
        )
        stock_move_obj = self.env["stock.move"]
        stock_move_obj._flush_search(outgoing_moves_domain)
        stock_move_obj.flush_model(["product_uom_qty"])

        move_query = stock_move_obj._where_calc(outgoing_moves_domain)
        stock_move_obj._apply_ir_rules(move_query, "read")

        move_tables, move_where, move_params = move_query.get_sql()

        move_sql = f"""
            SELECT
                {stock_move_obj._table}.product_id,
                SUM({stock_move_obj._table}.product_uom_qty) AS qty
            FROM {move_tables}
            JOIN avg_daily_usage ON avg_daily_usage.product_id =
                {stock_move_obj._table}.product_id
            WHERE {move_where}
            GROUP BY {stock_move_obj._table}.product_id
        """

        # -- STOCK MOVE (INCOMING) with condition on products ---
        # --- for which we have an average daily usage at the location ---
        incoming_moves_domain = location._get_replenishing_moves_domain()
        incoming_moves_domain = expression.AND(
            [incoming_moves_domain, [("date", "<=", horizon)]]
        )
        stock_move_obj._flush_search(incoming_moves_domain)

        move_in_query = stock_move_obj._where_calc(incoming_moves_domain)
        stock_move_obj._apply_ir_rules(move_in_query, "read")
        move_in_tables, move_in_where, move_in_params = move_in_query.get_sql()

        move_in_sql = f"""
            SELECT
                {stock_move_obj._table}.product_id,
                - SUM({stock_move_obj._table}.product_uom_qty) AS qty
            FROM {move_in_tables}
            JOIN avg_daily_usage ON avg_daily_usage.product_id =
                {stock_move_obj._table}.product_id
            WHERE {move_in_where}
            GROUP BY {stock_move_obj._table}.product_id
        """

        # --- STOCK QUANT with condition on products ---
        # --- for which we have an average daily usage at the location ---

        stock_quant_obj = self.env["stock.quant"]
        domain_quant, _im, _om = location._get_stock_domains()
        stock_quant_obj._flush_search(domain_quant)
        stock_quant_obj.flush_model(["quantity"])

        quant_query = stock_quant_obj._where_calc(domain_quant)
        stock_quant_obj._apply_ir_rules(quant_query, "read")

        quant_tables, quant_where, quant_params = quant_query.get_sql()

        quant_sql = f"""
            SELECT
                {stock_quant_obj._table}.product_id,
                - SUM({stock_quant_obj._table}.quantity) AS qty
            FROM {quant_tables}
            JOIN avg_daily_usage ON avg_daily_usage.product_id =
                {stock_quant_obj._table}.product_id
            WHERE {quant_where}
            GROUP BY {stock_quant_obj._table}.product_id
        """

        # --- FINAL UNION ---

        final_sql = f"""
            WITH avg_daily_usage AS ({adu_sql})
            SELECT product_id, SUM(qty) AS qty
            FROM (
                SELECT * FROM avg_daily_usage
                UNION ALL
                {move_sql}
                UNION ALL
                {move_in_sql}
                UNION ALL
                {quant_sql}
            ) AS combined
            GROUP BY product_id
            HAVING SUM(qty) > 0
        """

        params = adu_params + move_params + move_in_params + quant_params

        self.env.cr.execute(final_sql, params)
        return dict(self.env.cr.fetchall())
