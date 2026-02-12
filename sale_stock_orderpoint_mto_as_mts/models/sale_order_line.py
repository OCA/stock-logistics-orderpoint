# Copyright 2026 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from collections import defaultdict

from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        res = super()._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty
        )
        if self:
            self._ensure_default_orderpoints_for_mto()
        return res

    def _ensure_default_orderpoints_for_mto(self):
        mto_products_by_wh = defaultdict(lambda: self.product_id.browse())
        origins_by_wh_by_prod = defaultdict(lambda: defaultdict(list))
        for sol in self:
            for move in self.move_ids:
                route = sol.route_id or move.rule_id.route_id
                if (
                    route.is_mto
                    and move.picking_type_id.code == "outgoing"
                    and move.state not in ("draft", "done", "cancel")
                ):
                    wh = move.warehouse_id or sol.order_id.warehouse_id
                    mto_products_by_wh[wh] |= move.product_id
                    origins_by_wh_by_prod[wh][move.product_id].append(move.origin)
        for warehouse, mto_products in mto_products_by_wh.items():
            new_orderpoints = mto_products._ensure_default_orderpoint_for_mto(
                domain=[], warehouse=warehouse
            )
            # As orderpoint are created after the SO demand has been placed, we
            # need to run them if they are in auto trigger
            ops = new_orderpoints.filtered(lambda op: op.trigger == "auto")
            if ops and not self.env["ir.config_parameter"].sudo().get_param(
                "stock.no_auto_scheduler"
            ):
                origins = {
                    op.id: origins_by_wh_by_prod[warehouse][op.product_id] for op in ops
                }
                ops.with_context(origins=origins)._procure_orderpoint_confirm(
                    company_id=warehouse.company_id, raise_user_error=False
                )
