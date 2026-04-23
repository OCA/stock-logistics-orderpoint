# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models, tools

from odoo.addons.stock_available_location_get_domain.models.product_product import (
    extract_subdomains,
)
from odoo.addons.stock_location_orderpoint.models.stock_location_orderpoint_strategy import (
    StockLocationOrderpointStrategy,
)


class StockLocationOrderpoint(models.Model):

    _inherit = "stock.location.orderpoint"

    replenish_method = fields.Selection(
        selection_add=[("average_daily_usage", "Past Average Daily Usage")],
        ondelete={"average_daily_usage": "cascade"},
    )

    @property
    def _strategy_model(self) -> StockLocationOrderpointStrategy:
        self.ensure_one()
        if self.replenish_method == "average_daily_usage":
            return self.env["stock.location.orderpoint.strategy.average_daily_usage"]
        return super()._strategy_model

    # -------------------------------------------------------------------------
    # Orderpoint selection and domains
    # -------------------------------------------------------------------------

    @api.model
    @tools.ormcache("orderpoint_id")
    def _get_daily_usage_products_location_domain(self, orderpoint_id):
        """
        In the average daily sale strategy, we want to consider all the products that
        have an average daily usage at the destination location of the orderpoint as
        candidates to compute the demand for.

        :param orderpoint_id: int id of the orderpoint

        :return: list of tuples to use as domain to filter products
        """
        orderpoint = self.browse(orderpoint_id)
        (quant_domain, _il, _ol,) = orderpoint._product_model._get_domain_locations_new(
            [orderpoint.location_id.id]
        )
        return extract_subdomains(quant_domain, "location_id")

    # -------------------------------------------------------------------------
    # Cache lifecycle
    # -------------------------------------------------------------------------

    def _clear_caches(self):  # pylint: disable=missing-return
        super()._clear_caches()
        self._get_daily_usage_products_location_domain.clear_cache(self)
