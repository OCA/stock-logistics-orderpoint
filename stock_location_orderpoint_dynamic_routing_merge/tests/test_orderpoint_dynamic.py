# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase

from odoo.addons.queue_job.tests.common import trap_jobs

from .common import StockOrderpointDynamicMergeCommon


class TestStockOrderpointDynamicMerge(
    StockOrderpointDynamicMergeCommon, TransactionCase
):
    def test_orderpoint_with_dynamic_merge(self):
        """
        Create a reserve quantity for product
        """
        self._create_quantity(self.location_stock_reserve_food, 50.0)
        self._create_orderpoint(location_dest=self.stock, route_id=self.reserve_route)

        # Create an outgoing movement
        move_out = self.env["stock.move"].create(
            {
                "name": "Move OUT 1",
                "location_id": self.stock.id,
                "location_dest_id": self.customers.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 5.0,
            }
        )

        with trap_jobs() as trap:
            move_out._action_confirm()
            move_out._action_assign()
            trap.assert_jobs_count(1)
            trap.perform_enqueued_jobs()

        picking = self.env["stock.picking"].search(
            [("picking_type_id", "=", self.pick_type_reserve.id)]
        )

        self.assertTrue(picking)

        # TODO: Finish this (check if new move is merged with existing one)
