# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, models, tools
from odoo.osv import expression

from odoo.addons.stock_available_location_get_domain.models.product_product import (
    extract_subdomains,
)


class StockLocation(models.Model):
    _inherit = "stock.location"

    @api.model
    @tools.ormcache("location_id")
    def _get_daily_usage_products_location_domain(self, location_id):
        """
        In the average daily sale strategy, we want to consider all the products that
        have an average daily usage at the destination location of the orderpoint as
        candidates to compute the demand for.

        :param location_id: int id of the location

        :return: list of tuples to use as domain to filter products
        """

        quant_domain, _il, _ol = self.browse(location_id)._get_stock_domains()
        return extract_subdomains(quant_domain, "location_id")

    def _get_replenishing_moves_domain(self):
        """Get the domain to apply on stock.move to get the moves replenishing a location."""
        (
            _q,
            domain_move_in_loc,
            _ol,
        ) = self._get_stock_domains()
        domain = [
            ("state", "in", ("confirmed", "assigned", "partially_available")),
        ]
        return expression.AND([domain_move_in_loc, domain])

    # -------------------------------------------------------------------------
    # Cache lifecycle
    # -------------------------------------------------------------------------

    def _clear_caches(self):  # pylint: disable=missing-return
        super()._clear_caches()
        self._get_daily_usage_products_location_domain.clear_cache(self)
