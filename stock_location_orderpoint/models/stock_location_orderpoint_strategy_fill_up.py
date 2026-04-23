# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools import float_compare


class StockLocationOrderpointStrategyFillUp(models.AbstractModel):
    _inherit = "stock.location.orderpoint.strategy"
    _name = "stock.location.orderpoint.strategy.fill_up"
    _description = "Stock location orderpoint strategy: fill up to the max quantity"

    @api.model
    def _get_candidate_products(self, location, products=None):
        """
        In the fill-up strategy, if the orderpoint is triggered without specifying products,
        we want to consider only the products with pending not fully reserved moves
        from the destination location of the orderpoint as candidates to compute the demand for.
        This is because the fill-up strategy is meant to fill up the stock at the destination
        location, and if there are no pending moves for a product, it means that there is no
        demand for this product at the destination location.

        :param location: stock.location record
        :param products: product.product recordset or None

        :return: product.product recordset
        """
        if products:
            return products
        domain_move = self.env["stock.location"]._get_consuming_moves_domain(
            location.id
        )
        stock_move_obj = self.env["stock.move"]
        stock_move_obj._flush_search(domain_move)
        query = stock_move_obj._where_calc(domain_move)
        stock_move_obj._apply_ir_rules(query, "read")
        from_clause, where_clause, params = query.get_sql()
        sql = f"""
            SELECT DISTINCT product_id
            FROM {from_clause}
            WHERE {where_clause}
        """
        self.env.cr.execute(sql, params)
        product_ids = [row[0] for row in self.env.cr.fetchall()]
        return self.env["product.product"].browse(product_ids)

    @api.model
    def _compute_demand(self, location, products) -> dict[int, float]:
        """
        Compute demand for the given products according to the fill-up strategy.
        The demand is computed as the quantity required to ensure that the
        virtual available quantity is not negative, i.e. to fill
        up the stock up to 0. according to the quantity available at source
        location and the quantity already incoming.

        :param location: stock.location record
        :param products: product.product recordset
        """
        demand_data = {}
        qties_on_location = products.with_context(
            location=location.id
        )._compute_quantities_dict(None, None, None)
        for product_id, qties_on_location in qties_on_location.items():
            virtual_available_on_dest = qties_on_location["virtual_available"]
            if (
                float_compare(
                    virtual_available_on_dest,
                    0,
                    precision_rounding=self.env["product.product"]
                    .browse(product_id)
                    .uom_id.rounding,
                )
                >= 0
            ):
                continue
            demand_data[product_id] = abs(virtual_available_on_dest)
        return demand_data

    @api.model
    def _after_run_replenishment(self, location, replenishment_moves):
        """In the fill-up strategy, we want to set the date of the replenishment moves
        to the earliest date of the pending moves for the same product and the same
        destination location, to ensure that the replenishment is done in time to meet
        the demand of these pending moves.
        """
        replenishment_moves = super()._after_run_replenishment(
            location, replenishment_moves
        )
        domain_move = self.env["stock.location"]._get_consuming_moves_domain(
            location.id
        )
        stock_move_obj = self.env["stock.move"]
        stock_move_obj._flush_search(domain_move)
        stock_move_obj.flush_model(["date"])
        query = stock_move_obj._where_calc(domain_move)
        stock_move_obj._apply_ir_rules(query, "read")
        from_clause, where_clause, params = query.get_sql()
        sql = f"""
            SELECT product_id,
                  min (date)
            FROM {from_clause}
            WHERE {where_clause}
            GROUP BY product_id
        """
        self.env.cr.execute(sql, params)
        dates_by_product = {row[0]: row[1] for row in self.env.cr.fetchall()}
        picking_change_date_ids = set()
        for move in replenishment_moves:
            if move.product_id.id not in dates_by_product:
                continue
            move.date = dates_by_product[move.product_id.id]
            picking_change_date_ids.add(move.picking_id.id)
        pickings = self.env["stock.picking"].browse(picking_change_date_ids)
        for picking in pickings:
            picking_date = min(picking.move_ids.mapped("date"))
            if picking_date < picking.scheduled_date:
                picking.scheduled_date = picking_date
        return replenishment_moves
