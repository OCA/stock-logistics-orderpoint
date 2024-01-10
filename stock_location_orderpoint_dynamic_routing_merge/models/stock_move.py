# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from itertools import groupby

from odoo import models


class StockMove(models.Model):

    _inherit = "stock.move"

    def _action_confirm(self, merge=True, merge_into=False):
        """
        When moves are confirmed through location orderpoints,
        do the move merge as some moves for the same product
        are already in the asigned picking.
        """
        moves = super()._action_confirm(merge=merge, merge_into=merge_into)
        if self.env.context.get("from_orderpoint"):
            moves = moves._after_location_orderpoint_confirm_merge()
        return moves

    def _after_location_orderpoint_confirm_merge(self):
        sorted_moves_by_rule = sorted(self, key=lambda m: m.picking_id.id)
        moves_to_rereserve_ids = []
        new_moves = self.browse()
        for _picking_id, move_list in groupby(
            sorted_moves_by_rule, key=lambda m: m.picking_id.id
        ):
            moves = self.browse(m.id for m in move_list)
            merged_moves = moves._merge_moves()
            new_moves |= merged_moves
            if moves != merged_moves:
                for move in merged_moves:
                    if not move.quantity_done:
                        moves_to_rereserve_ids.append(move.id)
        if moves_to_rereserve_ids:
            moves_to_rereserve = self.browse(moves_to_rereserve_ids)
            moves_to_rereserve._do_unreserve()
            moves_to_rereserve.with_context(
                exclude_apply_dynamic_routing=True
            )._action_assign()
        return new_moves
