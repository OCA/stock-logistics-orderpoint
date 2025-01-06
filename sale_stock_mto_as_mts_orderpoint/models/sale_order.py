# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        res = super()._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty
        )
        self._run_orderpoints_for_mto_products()
        return res

    def _run_orderpoints_for_mto_products(self):
        mto_route = self.env.ref("stock.route_warehouse0_mto", raise_if_not_found=False)
        if not mto_route:
            return

        orderpoints_to_procure_ids = []
        for line in self:
            delivery_moves = line.move_ids.filtered(
                lambda m: m.picking_id.picking_type_code == "outgoing"
                and m.state not in ("done", "cancel")
            )
            for delivery_move in delivery_moves:
                if (
                    not delivery_move.is_from_mto_route
                    and mto_route not in delivery_move.product_id.route_ids
                ):
                    continue
                if not delivery_move.warehouse_id.mto_as_mts:
                    continue
                orderpoint = line._get_mto_orderpoint(delivery_move.product_id)
                if orderpoint.procure_recommended_qty:
                    orderpoints_to_procure_ids.append(orderpoint.id)

        orderpoints_to_procure = self.env["stock.warehouse.orderpoint"].browse(
            orderpoints_to_procure_ids
        )

        procurements = []

        for item in orderpoints_to_procure:
            if not item.procure_recommended_qty:
                continue
            if item.product_uom.rounding <= 0:
                continue

            values = item._prepare_procurement_values()
            values["date_planned"] = item.procure_recommended_date

            procurements.append(
                self.env["procurement.group"].Procurement(
                    item.product_id,
                    item.procure_recommended_qty,
                    item.product_uom,
                    item.location_id,
                    item.name,
                    item.name,
                    item.company_id,
                    values,
                )
            )

        if procurements:
            self.env["procurement.group"].run(procurements)

    def _get_mto_orderpoint(self, product_id):
        self.ensure_one()
        warehouse = self.warehouse_id or self.order_id.warehouse_id
        location = warehouse._get_locations_for_mto_orderpoints()
        orderpoint_model = self.env["stock.warehouse.orderpoint"].with_context(
            active_test=False
        )

        orderpoint = orderpoint_model.search_fetch(
            [("product_id", "=", product_id.id), ("location_id", "=", location.id)],
            ["active"],
            limit=1,
        )

        if orderpoint:
            if not orderpoint.active:
                orderpoint.write(
                    {"active": True, "product_min_qty": 0.0, "product_max_qty": 0.0}
                )
        else:
            orderpoint = orderpoint_model.sudo().create(
                {
                    "product_id": product_id.id,
                    "warehouse_id": warehouse.id,
                    "location_id": location.id,
                    "product_min_qty": 0.0,
                    "product_max_qty": 0.0,
                }
            )
        return orderpoint
