# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

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

    def _get_demand_products_by_location_orderpoint(self, trigger="auto"):
        """
        Triggered when demand appears in orderpoint locations.
        Return the products to replenish by orderpoint.
        :param trigger: the trigger to consider to select the orderpoints to replenish
        :return: dict {orderpoint: products}
        """
        # move from location consume order point location -> DO I've to replenish?
        moves_by_orderpoint = self._group_by_location_orderpoints(
            "location_id", "location_id", trigger=trigger
        )
        products_by_orderpoint = {}
        for orderpoint, orderpoint_moves in moves_by_orderpoint.items():
            orderpoint_moves = orderpoint_moves.filtered_domain(
                orderpoint._get_consuming_moves_domain()
            )
            if orderpoint_moves:
                products_by_orderpoint[orderpoint] = orderpoint_moves.product_id
        return products_by_orderpoint

    def _get_supply_products_by_location_orderpoint(self, trigger="auto"):
        """
        Triggered when supply arrives in orderpoint source locations.
        Return the products to replenish by orderpoint.
        :param trigger: the trigger to consider to select the orderpoints to replenish
        :return: dict {orderpoint: products}
        """
        # move to src location replenish order point source location -> DO I've
        # to replenish?
        moves_by_orderpoint = self._group_by_location_orderpoints(
            "location_dest_id", "location_src_id", trigger=trigger
        )
        products_by_orderpoint = {}
        for orderpoint, orderpoint_moves in moves_by_orderpoint.items():
            # We can ignore the unlimited case:
            # Without the limit, the source handles all the demand
            if not orderpoint.replenish_limit_to_free_qty:
                continue
            orderpoint_moves = orderpoint_moves.filtered_domain(
                orderpoint._get_supplying_moves_domain()
            )
            if orderpoint_moves:
                products_by_orderpoint[orderpoint] = orderpoint_moves.product_id
        return products_by_orderpoint

    def _get_rerouted_products_by_location_orderpoint(
        self, new_location_dest_id, trigger="auto"
    ):
        """
        Triggered when stock is rerouted out of orderpoint locations.
        After the reroute, the orderpoint location misses the stock
        these moves supplied.
        Must be called before the write applying `new_location_dest_id`.
        Return the products to replenish by orderpoint.
        :param new_location_dest_id: the id of the new destination
        :param trigger: the trigger to consider to select the orderpoints to replenish
        :return: dict {orderpoint: products}
        """
        # The stock these moves were bringing will never arrive at their
        # former destination: what was waiting for it there has to be
        # replenished from somewhere else.
        # => Read the former destination before the write replaces it.
        # A new destination inside the former one still receives the stock.
        new_path = self.env["stock.location"].browse(new_location_dest_id).parent_path
        rerouted = self.filtered(
            lambda move: not new_path.startswith(move.location_dest_id.parent_path)
            and move.state not in ("draft", "done", "cancel")
        )
        if not rerouted:
            return {}
        # the former destination is the location the orderpoint fills
        moves_by_orderpoint = rerouted._group_by_location_orderpoints(
            "location_dest_id", "location_id", trigger=trigger
        )
        return {
            orderpoint: moves.product_id
            for orderpoint, moves in moves_by_orderpoint.items()
        }

    def _prepare_auto_replenishment_for_outgoing_moves(self):
        products_by_orderpoint = self._get_demand_products_by_location_orderpoint(
            trigger="auto"
        )
        self._prepare_run_replenishment(products_by_orderpoint)

    def _prepare_auto_replenishment_for_incoming_moves(self):
        products_by_orderpoint = self._get_supply_products_by_location_orderpoint(
            trigger="auto"
        )
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

    def _group_by_location_orderpoints(
        self, location_field, orderpoint_location_field, trigger="auto"
    ):
        """Group these moves by the orderpoints whose
        `orderpoint_location_field` contains the moves' `location_field`"""
        moves_by_orderpoint = defaultdict(self.browse)
        if not self:
            # without locations, _get_orderpoints returns all the orderpoints
            return moves_by_orderpoint
        orderpoints = self.env["stock.location.orderpoint"]._get_orderpoints(
            trigger,
            locations=self[location_field],
            location_field=orderpoint_location_field,
        )
        for orderpoint in orderpoints:
            moves = orderpoint._filter_moves(
                self, location_field, orderpoint_location_field
            )
            if moves:
                moves_by_orderpoint[orderpoint] |= moves
        return moves_by_orderpoint

    def _prepare_auto_replenishment_for_rerouted_arrivals(self, new_location_dest_id):
        """Replenish the locations these moves stop bringing stock to

        Must be called before the write applying `new_location_dest_id`.

        The orderpoint's own move domain must not filter these moves: an
        arrival is harmless while it stays on course, and only becomes a
        shortage once its destination is rewritten. The trigger is the change,
        not the move.
        """
        products_by_orderpoint = self._get_rerouted_products_by_location_orderpoint(
            new_location_dest_id, trigger="auto"
        )
        # NOTE: jobs won't run before the write
        self._prepare_run_replenishment(products_by_orderpoint)

    def write(self, vals):
        # `_action_confirm` and `_action_done` evaluate the replenishment on the
        # locations the move had at that time. Any later rewrite of those
        # locations would otherwise leave the new ones untriggered.
        if "location_dest_id" in vals:
            self._prepare_auto_replenishment_for_rerouted_arrivals(
                vals["location_dest_id"]
            )

        MovesTouchTracker.add_ids(self.ids)
        res = super().write(vals)

        if "location_id" in vals:
            self.filtered(
                lambda move: move.state not in ("draft", "done", "cancel")
            )._prepare_auto_replenishment_for_outgoing_moves()
        return res

    def _action_confirm(self, *args, **kwargs):
        """This triggers the replenishment for newly confirmed moves"""
        moves = super()._action_confirm(*args, **kwargs)
        # A confirmed move is a need
        # -> it decreases the forecasted stock of its source location.
        # An orderpoint replenishes the forecast, not the reservation
        # -> the check belongs here and not in `_action_assign`.
        # NOTE: confirm may merge moves, so trigger on the returned records.
        moves._prepare_auto_replenishment_for_outgoing_moves()
        return moves

    def _action_done(self, *args, **kwargs):
        """
        This triggers the replenishment for waiting moves
        when the stock increases on a source location of an orderpoint
        """
        moves = super()._action_done(*args, **kwargs)
        # When a move is done, it means that the stock at the target location
        # is increased. So we need to trigger a check for replenishment
        # on this location IOW if an orderpoint exists for this location
        # as source location and the move has the expected characteristics
        # (state, ...)
        if moves:
            moves._prepare_auto_replenishment_for_incoming_moves()
        return moves

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
