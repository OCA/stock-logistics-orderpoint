# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _group_by_location_orderpoints(
        self, location_field, orderpoint_location_field, trigger="auto"
    ):
        """Group these move lines by the orderpoints whose
        `orderpoint_location_field` contains the move lines' `location_field`"""
        lines_by_orderpoint = defaultdict(self.browse)
        if not self:
            # without locations, _get_orderpoints returns all the orderpoints
            return lines_by_orderpoint
        orderpoints = self.env["stock.location.orderpoint"]._get_orderpoints(
            trigger,
            locations=self[location_field],
            location_field=orderpoint_location_field,
        )
        for orderpoint in orderpoints:
            lines = orderpoint._filter_moves(
                self, location_field, orderpoint_location_field
            )
            if lines:
                lines_by_orderpoint[orderpoint] |= lines
        return lines_by_orderpoint

    def _get_rerouted_products_by_location_orderpoint(
        self, new_location_dest_id, trigger="auto"
    ):
        """
        Triggered when stock is rerouted out of orderpoint locations.
        After the reroute, the orderpoint location misses the stock
        these move lines supplied.
        Must be called before the write applying `new_location_dest_id`.
        Return the products to replenish by orderpoint.
        :param new_location_dest_id: the id of the new destination
        :param trigger: the trigger to consider to select the orderpoints to replenish
        :return: dict {orderpoint: products}
        """
        # Done move lines hold stock: changing their destination moves it.
        # A new destination inside the former one still holds the stock.
        new_path = self.env["stock.location"].browse(new_location_dest_id).parent_path
        rerouted = self.filtered(
            lambda line: (
                line.state == "done"
                and not new_path.startswith(line.location_dest_id.parent_path)
            )
        )
        # the former destination is the location the orderpoint fills
        lines_by_orderpoint = rerouted._group_by_location_orderpoints(
            "location_dest_id", "location_id", trigger=trigger
        )
        return {
            orderpoint: lines.product_id
            for orderpoint, lines in lines_by_orderpoint.items()
        }

    def _get_supply_products_by_location_orderpoint(self, trigger="auto"):
        """
        Triggered when supply arrives in orderpoint source locations.
        Return the products to replenish by orderpoint.
        :param trigger: the trigger to consider to select the orderpoints to replenish
        :return: dict {orderpoint: products}
        """
        done_lines = self.filtered(lambda line: line.state == "done")
        lines_by_orderpoint = done_lines._group_by_location_orderpoints(
            "location_dest_id", "location_src_id", trigger=trigger
        )
        return {
            orderpoint: lines.product_id
            for orderpoint, lines in lines_by_orderpoint.items()
            # We can ignore the unlimited case:
            # Without the limit, the source handles all the demand
            if orderpoint.replenish_limit_to_free_qty
        }

    def write(self, vals):
        # Changing the destination of done move lines moves their stock:
        # the former destination loses it and the new one receives it.
        if "location_dest_id" not in vals:
            return super().write(vals)
        moves = self.move_id
        moves._prepare_run_replenishment(
            self._get_rerouted_products_by_location_orderpoint(
                vals["location_dest_id"], trigger="auto"
            )
        )
        res = super().write(vals)
        moves._prepare_run_replenishment(
            self._get_supply_products_by_location_orderpoint(trigger="auto")
        )
        return res
