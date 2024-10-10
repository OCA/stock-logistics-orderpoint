# Copyright 2024 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import _, api, models

from odoo.addons.queue_job.job import identity_exact

_logger = logging.getLogger(__name__)


class StockLocationOrderpoint(models.Model):

    _inherit = "stock.location.orderpoint"

    def _get_moves_to_cleanup_domain(self) -> list:
        return [
            ("location_orderpoint_id", "in", self.ids),
            ("state", "not in", ("done", "cancel")),
            ("quantity_done", "<=", 0),
            ("picking_id.printed", "=", False),
        ]

    def _get_moves_to_cleanup(self):
        moves = self.env["stock.move"].search(self._get_moves_to_cleanup_domain())
        return moves

    def cleanup(self, run_after=False):
        """
        This method will launch the cleanup process as a queue job.
        """
        for orderpoint in self:
            description = _(
                "Running the cleanup for the orderpoint %(orderpoint_name)s",
                orderpoint_name=orderpoint.name,
            )
            orderpoint.with_delay(
                description=description, identity_key=identity_exact
            )._cleanup(run_after=run_after)

    def _cleanup(self, run_after=False):
        """
        run_after: Run the orderpoint after cleanup
        """

        moves = self._get_moves_to_cleanup()
        for picking, moves in moves.partition("picking_id").items():
            moves.exists()._action_cancel()
            picking._log_location_orderpoint_cleanup_message(self, moves)

        if run_after:
            self.run_replenishment()

    @api.model
    def run_cleanup(self, orderpoints=False, run_after=False):
        """
        This method should be called by crons
        """
        self.browse(orderpoints).cleanup(run_after=run_after)

    @api.model
    def run_cleanup_method(self, replenish_method="fill_up", run_after=False):
        """
        This method should be called by crons.

        e.g.: We have plenty of orderpoints but we know which replenish method
              should be cleaned.
        """
        if replenish_method not in self._fields["replenish_method"].get_values(
            self.env
        ):
            _logger.warning(
                "You try to call 'run_cleanup_method' with an undefined replenish method '%s'",
                replenish_method,
            )
        self.search([("replenish_method", "=", replenish_method)]).cleanup(
            run_after=run_after
        )

    def get_cleanup_action(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_location_orderpoint_cleanup.stock_location_orderpoint_cleanup_act_window"
        )
        return action
