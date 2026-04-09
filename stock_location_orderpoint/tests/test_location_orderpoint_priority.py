# Copyright 2023 ACSONE SA/NV (http://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo.addons.queue_job.job import identity_exact
from odoo.addons.queue_job.tests.common import trap_jobs

from .common import TestLocationOrderpointCommon


class TestLocationOrderpointPriority(TestLocationOrderpointCommon):
    def test_mixed_replenishment_priority(self):
        """
        Create a manual orderpoint with 'normal' priority

        Create moves that will generate replenishment (ougoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Make the orderpoint an automatic orderpoint with 'urgent' priority

        Change the existing outgoing move quantity (with lower need)

        Create an outgoing move with the difference quantity (no move should be created)

        Check that the replenishment move priority has changed to 'urgent'.
        """
        job_func = self.env["stock.location.orderpoint"].run_auto_replenishment
        move_qty = 12

        manual_orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="manual",
        )
        out_move = self._create_outgoing_move(move_qty)
        self._create_incoming_move(move_qty, location_src)
        manual_orderpoint.run_replenishment()
        replenish_move_manual = self._get_replenishment_move(manual_orderpoint)

        self.assertTrue(replenish_move_manual)
        self.assertEqual(12.0, replenish_move_manual.product_uom_qty)
        self.assertEqual("0", replenish_move_manual.priority)

        # Change the outgoing quantity
        out_move.product_uom_qty = 6.0

        self.assertEqual(6.0, out_move.product_uom_qty)

        manual_orderpoint.update(
            {
                "trigger": "auto",
                "priority": "1",
            }
        )

        with trap_jobs() as trap:
            out_move_2 = self._create_outgoing_move(2.0)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                manual_orderpoint.browse([]).run_auto_replenishment,
                args=(out_move_2.product_id, out_move_2.location_id, "location_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            trap.perform_enqueued_jobs()

        replenish_move = self._get_replenishment_move(manual_orderpoint)
        self.assertEqual(replenish_move, replenish_move_manual)

        self.assertEqual(replenish_move.product_uom_qty, 12.0)

        # Check priority has been changed
        self.assertEqual("1", replenish_move.priority)

    def test_mixed_replenishment_priority_two_products(self):
        """
        Create a manual orderpoint with 'normal' priority

        Create moves that will generate replenishment (outgoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Update orderpoint priority to 'urgent'

        Change the existing outgoing move quantity (with lower need)

        Create an outgoing move with the difference quantity (no move should be created)

        Check that both replenishment moves priority has changed to 'urgent'.
        """
        product_1 = self.product
        product_2 = self.env["product.product"].create(
            {
                "name": "Product 2",
                "type": "product",
            }
        )
        move_qty = 12

        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="manual",
        )
        out_move = self._create_outgoing_move(move_qty)
        self._create_incoming_move(move_qty, location_src)

        self.product = product_2
        self._create_outgoing_move(move_qty, product=product_2)
        self._create_incoming_move(move_qty, location_src, product=product_2)

        orderpoint.run_replenishment()

        replenish_move_manual_1 = self._get_replenishment_move(
            orderpoint, product=product_1
        )
        replenish_move_manual_2 = self._get_replenishment_move(
            orderpoint, product=product_2
        )

        self.assertTrue(replenish_move_manual_1)
        self.assertTrue(replenish_move_manual_2)

        # Change the outgoing quantity
        out_move.product_uom_qty = 6.0
        self.assertEqual(6.0, out_move.product_uom_qty)

        orderpoint.priority = "1"

        self.product = product_1
        self._create_outgoing_move(2.0)

        orderpoint.run_replenishment()

        replenish_move = self._get_replenishment_move(orderpoint, product=product_1)
        replenish_move_2 = self._get_replenishment_move(orderpoint, product=product_2)

        self.assertEqual(replenish_move, replenish_move_manual_1)
        self.assertEqual(replenish_move.product_uom_qty, 12.0)

        # Check priority has been changed (for both moves)
        self.assertEqual("1", replenish_move.priority)
        self.assertEqual("1", replenish_move_2.priority)

    def test_merged_replenishment_move_priority(self):
        """
        Test that merged replenishment moves coming from different orderpoints
        inherit the highest priority orderpoint.

        Setup:
            - Create a manual orderpoint with priotity 0
            - Create a manual orderpoint with priotity 1 (same location as 1st one)
            - Create a shortage on orderpoints location
            - trigger orderpoint 0 for replenishment
            - Create a shortage on location again
            - Trigger orderpoint 1 for replenishment

        Expected result:
            - The resulting merged repl move to account for both shortage set on
              location should be linked to orderpoint '1' (and have a priority of '1')
        """

        # ↓ we drop the unique constraint here because ideally we want to create
        # orderpoints that have exactly the same characteristics except for the
        # replenish_method (in order to make sure the moves get merged)
        # However, we only have 1 replenish_method available and we do not want to
        # add another dependency (e.g. avg_daily_sale)
        self.env.cr.execute(
            """
            ALTER TABLE stock_location_orderpoint
            DROP CONSTRAINT stock_location_orderpoint_location_route_unique;
            """
        )

        (
            manual_orderpoint_1,
            orderpoints_src_location,
        ) = self._create_orderpoint_complete(
            "Reserve",
            trigger="manual",
        )
        manual_orderpoint_2 = manual_orderpoint_1.copy({"priority": "1"})

        self.assertEqual(
            manual_orderpoint_1.location_id, manual_orderpoint_2.location_id
        )
        self.assertEqual(
            manual_orderpoint_1.location_src_id, manual_orderpoint_2.location_src_id
        )
        self.assertEqual(manual_orderpoint_1.route_id, manual_orderpoint_2.route_id)

        # Make some stock in the orderpoints sources
        self._create_incoming_move(100, orderpoints_src_location)

        # create a move that introduces a shortage on orderpoints location
        self._create_outgoing_move(20)

        # trigger creation of first orderpoint repl move
        manual_orderpoint_1.run_replenishment()
        repl_move = self._get_replenishment_move(manual_orderpoint_1)
        self._assert_replenishment_move(repl_move, 20, manual_orderpoint_1)

        # introduce shortage again on orderpoints location
        self._create_outgoing_move(20)

        # trigger creation of first orderpoint repl move
        manual_orderpoint_2.run_replenishment()
        self._assert_replenishment_move(repl_move, 40, manual_orderpoint_2)
