# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class StockLocationOrderpointStrategy(models.AbstractModel):
    _name = "stock.location.orderpoint.strategy"
    _description = "Stock location orderpoint strategy"

    @api.model
    def _get_candidate_products(self, location, products=None):
        """
        Get the candidate products to compute the demand for according to a specific strategy.
        By default, we consider that all stockable products are candidates.

        :param location: stock.location record
        :param products: product.product recordset or None

         :return: product.product recordset

        When the method is called with products, it's responsible to filter
        them according to the strategy logic.
        """
        raise NotImplementedError(
            "The _get_candidate_products method should be implemented in the strategy"
        )

    @api.model
    def _compute_demand(self, location, products) -> dict[int, float]:
        """
        Compute demand for the given products according to a specific strategy.

        :param location: stock.location record
        :param products: product.product recordset

        :return: dict {product_id: demand_qty}

        This model is meant to be inherited to implement different strategies
        to compute the demand.
        The demand is the quantity to replenish to meet the orderpoint's rules.
        """
        raise NotImplementedError(
            "The _compute_demand method should be implemented in the strategy."
        )

    @api.model
    def _after_run_replenishment(self, location, replenishment_moves):
        """
        Method called after the replenishment moves have been created for an orderpoint.
        This allows to implement specific logic after the replenishment, like changing the
        priority of the replenishment moves according to the strategy.

        :param location: stock.location record
        :param replenishment_moves: stock.move recordset of the replenishment moves that
        have been created
        """
        return replenishment_moves
