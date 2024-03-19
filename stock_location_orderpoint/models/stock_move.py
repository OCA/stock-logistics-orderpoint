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
        self._prepare_auto_replenishment("location_id")

    def _prepare_auto_replenishment_for_incoming_moves(self):
        self._prepare_auto_replenishment("location_dest_id")

    def _prepare_auto_replenishment(self, location_field):
        if not self or self.env.context.get("skip_auto_replenishment"):
            return
        locations_products = defaultdict(set)
        location_ids = set()
        product_obj = self.env["product.product"]

        moves = self.env[
            "stock.location.orderpoint"
        ]._filter_moves_triggering_orderpoints(self, trigger="auto")
        for move in moves:
            location = getattr(move, location_field)
            locations_products[location].add(move.product_id.id)
            location_ids.add(location.id)
        # Map the the move's location field
        # to the correspoding stock.location.orderpoint's location field
        location_field = (
            location_field == "location_id" and location_field or "location_src_id"
        )
        for location, products in locations_products.items():
            # if not orderpoints._is_location_parent_of(location, location_field):
            #    continue
            for product in product_obj.browse(products):
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

    def _action_assign(self, *args, **kwargs):
        """This triggers the replenishment for new moves which are waiting for stock"""
        res = super()._action_assign(*args, **kwargs)
        # When a move is assigned, it means that the stock is available on the
        # location is decreased. So we need to trigger a check for replenishment
        # on this location IOW if an orderpoint exists for this location as
        # target location and the move has the expected characteristics (state, ...)
        self._prepare_auto_replenishment_for_outgoing_moves()
        return res

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
