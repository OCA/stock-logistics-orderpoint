# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import _, fields, models
from odoo.tools import ormcache

from odoo.addons.queue_job.job import identity_exact


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
        moves = self.env[
            "stock.location.orderpoint"
        ]._filter_moves_triggering_orderpoints(self, trigger="auto")
        self._enqueue_auto_replenishment_jobs(
            moves._collect_orderpoint_locations_products("location_id"),
            # the move leaves the location the orderpoint fills
            "location_id",
        )

    def _prepare_auto_replenishment_for_incoming_moves(self):
        moves = self.env[
            "stock.location.orderpoint"
        ]._filter_moves_triggering_orderpoints(self, trigger="auto")
        self._enqueue_auto_replenishment_jobs(
            moves._collect_orderpoint_locations_products("location_dest_id"),
            # the move arrives in the location the orderpoint takes stock from
            "location_src_id",
        )

    def _collect_orderpoint_locations_products(self, location_field):
        """Group the products of `self` by the location of `location_field`"""
        if not self or self.env.context.get("skip_auto_replenishment"):
            return {}
        locations_products = defaultdict(set)
        product_obj = self.env["product.product"]

        for move in self:
            location = getattr(move, location_field)
            locations_products[location].add(move.product_id.id)
        return {
            location: product_obj.browse(product_ids)
            for location, product_ids in locations_products.items()
        }

    def _enqueue_auto_replenishment_jobs(self, locations_products, location_field):
        if self.env.context.get("skip_auto_replenishment"):
            return
        for location, products in locations_products.items():
            # if not orderpoints._is_location_parent_of(location, location_field):
            #    continue
            for product in products:
                self._enqueue_auto_replenishment(
                    location, product, location_field
                ).delay()

    def _enqueue_auto_replenishment(
        self, location, product, location_field, **job_options
    ):
        """Enqueue a job stock.location.orderpoint.run_auto_replenishment()

        Can be extended to pass different options to the job (priority, ...).
        The usage of `.setdefault` allows to override the options set by default.

        return: a `Job` instance
        """
        job_options = job_options.copy()
        job_options.setdefault(
            "description",
            _(
                "Try to replenish quantities %(in_or_out)s location %(location_name)s "
                "for product %(product_name)s"
            )
            % {
                "in_or_out": location_field == "location_id" and _("in") or _("from"),
                "location_name": location.display_name,
                "product_name": product.display_name,
            },
        )
        # do not enqueue 2 jobs for the same location and product set
        job_options.setdefault("identity_key", identity_exact)
        delayable = self.env["stock.location.orderpoint"].delayable(**job_options)
        job = delayable.run_auto_replenishment(
            product,
            location,
            location_field,
        )
        return job

    def _prepare_auto_replenishment_for_rerouted_arrivals(self, new_location_dest_id):
        """Replenish the locations these moves stop bringing stock to

        Must be called before the write applying `new_location_dest_id`.

        `_filter_moves_triggering_orderpoints` must not filter these moves: an
        arrival is harmless while it stays on course, and only becomes a
        shortage once its destination is rewritten. The trigger is the change,
        not the move.
        """
        # The stock these moves were bringing will never arrive at their
        # former destination: what was waiting for it there has to be
        # replenished from somewhere else.
        # => Read the former destination before the write replaces it.
        rerouted = self.filtered(
            lambda move: move.location_dest_id.id != new_location_dest_id
            and move.state not in ("draft", "done", "cancel")
        )
        if not rerouted:
            return
        orderpoints = self.env["stock.location.orderpoint"]._get_orderpoints(
            "auto", locations=rerouted.location_dest_id, location_field="location_id"
        )
        if not orderpoints:
            return
        rerouted = rerouted.filtered(
            lambda move: orderpoints._is_location_parent_of(
                move.location_dest_id, "location_id"
            )
        )
        # => We need to replenish these location later
        # NOTE: jobs won't run before the write
        self._enqueue_auto_replenishment_jobs(
            rerouted._collect_orderpoint_locations_products("location_dest_id"),
            # the former destination is the location the orderpoint fills
            "location_id",
        )

    def write(self, vals):
        # `_action_confirm` and `_action_done` evaluate the replenishment on the
        # locations the move had at that time. Any later rewrite of those
        # locations would otherwise leave the new ones untriggered.

        if "location_dest_id" in vals:
            self._prepare_auto_replenishment_for_rerouted_arrivals(
                vals["location_dest_id"]
            )

        res = super().write(vals)

        if "location_dest_id" in vals:
            self.filtered(
                lambda move: move.state == "done"
            )._prepare_auto_replenishment_for_incoming_moves()

        if "location_id" in vals:
            # `waiting` is excluded: an upstream move already supplies it.
            self.filtered(
                lambda move: move.state not in ("draft", "waiting", "done", "cancel")
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
        moves._prepare_auto_replenishment_for_incoming_moves()
        return moves
