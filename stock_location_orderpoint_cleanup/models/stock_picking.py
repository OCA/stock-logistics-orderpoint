# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class StockPicking(models.Model):

    _inherit = "stock.picking"

    def _log_location_orderpoint_cleanup_message(self, orderpoint, moves):
        """
        This will log the moves that have been canceled through the cleanup
        process.
        """
        self.ensure_one()
        orderpoint_name = orderpoint.name
        moves_name = ",".join(moves.mapped("product_id.name"))
        message = _(
            "These moves have been cleaned up for location orderpoint "
            "%(orderpoint_name)s: %(moves_name)s",
            orderpoint_name=orderpoint_name,
            moves_name=moves_name,
        )
        self.message_post(body=message, message_type="comment")
