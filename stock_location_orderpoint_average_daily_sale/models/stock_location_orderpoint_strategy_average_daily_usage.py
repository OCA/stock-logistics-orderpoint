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
    def _get_candidate_products(self, location, products=None):
        """
        In the average daily usage strategy, if the orderpoint is triggered without
        specifying products, we don't return products. Indeed, the candidate products will be
        determined at the demand computation step, based on the products for which we have an
        average daily usage at the destination location of the orderpoint. If no product is
        passed to the demand method, it means that the orderpoint has been triggered for
        all products.

        :param location: stock.location record

        :return: product.product recordset
        """
        return products

    @api.model
    def _compute_demand(self, location, products) -> dict[int, float]:
        """
        Compute demand for the given products according to the average daily usage strategy.
        The demand is computed based on the past average daily usage at the destination location
        of the orderpoint minus the quantity still available at the location,
        plus the quantity already leaving the location.

        :param location: stock.location record
        :param products: product.product recordset
        """
        # --- STOCK AVERAGE DAILY SALE ---

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

        stock_avg_daily_sale_obj = self.env["stock.average.daily.sale"]
        stock_avg_daily_sale_obj._flush_search(domain)
        ads_query = stock_avg_daily_sale_obj._where_calc(domain)
        stock_avg_daily_sale_obj._apply_ir_rules(ads_query, "read")

        # join location
        loc_alias = ads_query.join(
            stock_avg_daily_sale_obj._table,
            "location_id",
            stock_location_obj._table,
            "id",
            "locations",
        )
        expression.expression(location_domain, stock_location_obj, loc_alias, ads_query)

        # join config
        stock_avg_cfg_obj = self.env["stock.average.daily.sale.config"]
        avg_cfg_alias = ads_query.join(
            stock_avg_daily_sale_obj._table,
            "config_id",
            stock_avg_cfg_obj._table,
            "id",
            "avg_cfg",
        )

        ads_tables, ads_where, ads_params = ads_query.get_sql()

        ads_sql = f"""
            SELECT
                {stock_avg_daily_sale_obj._table}.product_id,
                GREATEST(
                    (
                        (
                            {avg_cfg_alias}.number_days_qty_in_stock
                            *
                            {stock_avg_daily_sale_obj._table}.average_daily_qty
                        )
                        +
                        ({stock_avg_daily_sale_obj._table}.daily_standard_deviation
                        * {avg_cfg_alias}.safety_factor
                        * sqrt({avg_cfg_alias}.number_days_qty_in_stock))
                    ),
                    {avg_cfg_alias}.number_days_qty_in_stock
                    * {stock_avg_daily_sale_obj._table}.average_qty_by_sale
                ) AS qty
            FROM {ads_tables}
            WHERE {ads_where}
        """

        # --- STOCK MOVE (OUTGOING) ---

        outgoing_moves_domain = location._get_consuming_moves_domain(location.id)
        if products is not None:
            outgoing_moves_domain = expression.AND(
                [outgoing_moves_domain, [("product_id", "in", products.ids)]]
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
            WHERE {move_where}
            GROUP BY {stock_move_obj._table}.product_id
        """

        # --- STOCK QUANT ---

        stock_quant_obj = self.env["stock.quant"]
        domain_quant, _im, _om = location._get_stock_domains(location.id)
        if products is not None:
            domain_quant = expression.AND(
                [domain_quant, [("product_id", "in", products.ids)]]
            )
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
            WHERE {quant_where}
            GROUP BY {stock_quant_obj._table}.product_id
        """

        # --- FINAL UNION ---

        final_sql = f"""
            SELECT product_id, SUM(qty) AS qty
            FROM (
                {ads_sql}
                UNION ALL
                {move_sql}
                UNION ALL
                {quant_sql}
            ) AS combined
            GROUP BY product_id
            HAVING SUM(qty) > 0
        """

        params = ads_params + move_params + quant_params

        self.env.cr.execute(final_sql, params)
        return dict(self.env.cr.fetchall())
