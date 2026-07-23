# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.tools import ormcache

from odoo.addons.queue_job.job import identity_exact

from .tools import MovesTouchTracker


class StockMove(models.Model):
    _inherit = "stock.move"

    location_orderpoint_id = fields.Many2one(
        "stock.location.orderpoint", "Stock location orderpoint", index=True
    )

    @ormcache("self", "product")
    def _get_location_orderpoint_replenishment_date(self, product):
        return min(
            self.filtered(lambda move: move.product_id == product).mapped("date")
        )

    def _prepare_auto_replenishment_for_outgoing_moves(self):
        products_by_orderpoint = self.env[
            "stock.location.orderpoint"
        ]._get_from_move_demand(self, trigger="auto")
        self._prepare_run_replenishment(products_by_orderpoint)

    def _prepare_auto_replenishment_for_incoming_moves(self):
        products_by_orderpoint = self.env[
            "stock.location.orderpoint"
        ]._get_from_move_supply(self, trigger="auto")
        self._prepare_run_replenishment(products_by_orderpoint)

    def _prepare_run_replenishment(self, products_by_orderpoint):
        if not self or self.env.context.get("skip_auto_replenishment"):
            return
        for orderpoint, products in products_by_orderpoint.items():
            for product in products:
                self._enqueue_run_replenishment(
                    orderpoint,
                    product,
                ).delay()

    def _enqueue_run_replenishment(self, orderpoint, product, **job_options):
        """
        Enqueue a replenishment job for a single (orderpoint, product) pair.

        This is the delay point for AUTO orderpoints. It fires *before* the
        replenishment pipeline so that the full computation (candidate selection,
        demand, available qty, procurement) only happens inside a worker, and
        only for products whose move actually impacts an orderpoint. The identity
        key deduplicates concurrent triggers for the same (orderpoint, product).

        Design note — two delay mechanisms coexist intentionally:

        1. This method (AUTO, delay before pipeline):
           - Granularity: one job per (orderpoint × product).
           - Purpose: avoid redundant demand calculations for products that do
             not impact any orderpoint, and deduplicate concurrent stock.move
             events that concern the same (orderpoint, product) pair.
           - The entire _run_replenishment() pipeline runs synchronously inside
             the worker; procurement execution is therefore also synchronous.

        2. _enqueue_fulfill_procurement() (CRON / MANUAL, delay after demand):
           - Granularity: one job per (orderpoint x product) that has
             non-zero demand.
           - Purpose: defer the costly fulfillment step while keeping the
             availability check, procurement qty decision and procurement run
             in the same worker transaction.
           - Demand is computed in the caller transaction; each delayed job
             then executes _fulfill_procurement(product_id, demand_qty).

        Merging the two would require creating one job per candidate product
        before demand is computed, producing tens of thousands of unnecessary
        jobs on large databases (observed: 10,000+ jobs for ~300 actual
        replenishments on a production database using the daily-sale strategy).

        Can be extended to pass different options to the job (priority, …).
        The usage of `.setdefault` allows callers to override the defaults.

        :return: a Job instance (not yet delayed — caller must call .delay())
        """
        job_options = job_options.copy()
        job_options.setdefault(
            "description",
            _(
                "Try to replenish quantities in location %(location_name)s "
                "for product %(product_name)s"
            )
            % {
                "location_name": orderpoint.location_id.display_name,
                "product_name": product.display_name,
            },
        )
        # do not enqueue 2 jobs for the same location and product set
        job_options.setdefault("identity_key", identity_exact)
        delayable = orderpoint.delayable(**job_options)
        return delayable.run_replenishment(product)

    def _action_assign(self, *args, **kwargs):
        """This triggers the replenishment for new moves which are waiting for stock"""
        res = super()._action_assign(*args, **kwargs)
        # When a move is assigned, it means that the stock is available on the
        # location is decreased. So we need to trigger a check for replenishment
        # on this location IOW if an orderpoint exists for this location as
        # target location and the move has the expected characteristics (state, ...)
        if self:
            self._prepare_auto_replenishment_for_outgoing_moves()
        return res

    def _action_done(self, *args, **kwargs):
        """
        This triggers the replenishment for waiting moves
        when the stock increases on a source location of an orderpoint
        """
        moves = super()._action_done(*args, **kwargs)
        if moves:
            # When a move is done, it means that the stock at the target location
            # is increased. So we need to trigger a check for replenishment
            # on this location IOW if an orderpoint exists for this location
            # as source location and the move has the expected characteristics
            # (state, ...)
            moves._prepare_auto_replenishment_for_incoming_moves()
            # When a move is done, it means that the stock at the target location
            # is increased. So we need to trigger a check for cancellation of
            # not-yet-started replenishment moves for orderpoints whose demand
            # is already fulfilled by the stock these moves just brought to an
            # orderpoint's location.
            moves._prepare_cancel_fulfilled_replenishment_moves()
        return moves

    def _prepare_cancel_fulfilled_replenishment_moves(self):
        """
        This triggers the cancellation of not-yet-started replenishment
        moves when the demand they were created for is already fulfilled
        by the stock these moves just brought to an orderpoint's location.
        """
        moves = self._get_moves_to_check_for_cancel_fulfilled_replenishment()
        if not moves:
            return
        orderpoint_model = self.env["stock.location.orderpoint"]
        triggers = orderpoint_model._fields["trigger"].selection
        products_by_orderpoint = {}
        for trigger, _label in triggers:
            products_by_orderpoint.update(
                orderpoint_model._get_from_move_fulfillment(moves, trigger=trigger)
            )
        if not products_by_orderpoint:
            return
        # Respect the orderpoints' sequence (priority desc, sequence) so that
        # jobs are enqueued in the same order the replenishment pipeline
        # itself would process these orderpoints.
        orderpoints = orderpoint_model.concat(*products_by_orderpoint.keys()).sorted()
        for orderpoint in orderpoints:
            self._enqueue_cancel_fulfilled_replenishment_moves(
                orderpoint, products_by_orderpoint[orderpoint]
            ).delay()

    def _get_moves_to_check_for_cancel_fulfilled_replenishment(self):
        """
        Hook to exclude moves that must not trigger the cancellation of
        not-yet-started replenishment moves.

        Moves that are themselves replenishment moves generated by an
        orderpoint (location_orderpoint_id set) are excluded by default:
        doing such a move is an internal continuation of the replenishment
        itself (e.g. a partial delivery followed by a backorder), not an
        external fulfillment of the demand, and must not cancel its own
        backorder.

        :return: stock.move recordset to actually check
        """
        return self.filtered(lambda move: not move.location_orderpoint_id)

    def _enqueue_cancel_fulfilled_replenishment_moves(
        self, orderpoint, products, **job_options
    ):
        """
        Enqueue a job to cancel the not-yet-started replenishment moves of
        an orderpoint whose demand is already fulfilled.

        :param orderpoint: stock.location.orderpoint record
        :param products: product.product recordset to check
        :return: a Job instance (not yet delayed — caller must call .delay())
        """
        job_options = job_options.copy()
        job_options.setdefault(
            "description",
            _(
                "Check if replenishment moves in location %(location_name)s "
                "are still needed for %(product_count)s product(s)"
            )
            % {
                "location_name": orderpoint.location_id.display_name,
                "product_count": len(products),
            },
        )
        job_options.setdefault("identity_key", identity_exact)
        delayable = orderpoint.delayable(**job_options)
        return delayable._cancel_fulfilled_replenishment_moves(products)

    def _merge_moves_fields(self):
        # Make sure to link to the highest-priority orderpoint.
        # This ensures the merged move inherits the correct priority
        res = super()._merge_moves_fields()
        res["location_orderpoint_id"] = max(
            self, key=lambda x: x.location_orderpoint_id.priority
        ).location_orderpoint_id
        return res

    @api.model_create_multi
    @api.returns("self", lambda value: value.id)
    def create(self, vals_list):
        res = super().create(vals_list)
        MovesTouchTracker.add_ids(res.ids)
        return res

    def write(self, vals):
        MovesTouchTracker.add_ids(self.ids)
        return super().write(vals)
