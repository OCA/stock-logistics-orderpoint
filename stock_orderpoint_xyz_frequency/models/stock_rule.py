# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.fields import Domain


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.model
    def _get_orderpoint_domain(self, company_id=False):
        """Hide the postponed products from the procurement scheduler.

        Only _run_scheduler_tasks calls this, so the cadence gates the daily
        cron and nothing else: the "Order Once" button and the exception
        procurements go through _procure_orderpoint_confirm directly.
        """
        # Domain.AND, since super() still returns a plain list of terms.
        domain = super()._get_orderpoint_domain(company_id=company_id)
        skip_domain = self.env[
            "xyz.classification.product.level"
        ]._get_orderpoint_skip_domain(company_id=company_id)
        return Domain.AND([domain, skip_domain])

    @api.model
    def _run_scheduler_tasks(self, use_new_cursor=False, company_id=False):
        # The products are read before the run and stamped after it: a crashed
        # run then leaves the windows untouched and they are retried tomorrow.
        products = (
            self.env["stock.warehouse.orderpoint"]
            .search(self._get_orderpoint_domain(company_id=company_id))
            .product_id
        )
        res = super()._run_scheduler_tasks(
            use_new_cursor=use_new_cursor, company_id=company_id
        )
        self.env[
            "xyz.classification.product.level"
        ]._mark_replenishment_run_for_products(products, company_id=company_id)
        return res
