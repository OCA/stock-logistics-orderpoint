# Copyright 2023 ACSONE SA/NV (http://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import datetime

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

        Refill available quantity in reserve location

        Create an outgoing move (no move should be created)

        Launch the replenishment

        Check that the replenishment move has been  updated to 'urgent'
        and the qty to replenish is updated according to the new
        outgoing move qty.
        """
        move_qty = 12

        manual_orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="manual",
            proc_run_async=False,
        )
        self._create_outgoing_move(move_qty)
        self._create_incoming_move(move_qty, location_src)
        manual_orderpoint.run_replenishment()
        replenish_move_manual = self._get_replenishment_move(manual_orderpoint)

        self.assertTrue(replenish_move_manual)
        self.assertEqual(12.0, replenish_move_manual.product_uom_qty)
        self.assertEqual("0", replenish_move_manual.priority)

        manual_orderpoint.update(
            {
                "trigger": "auto",
                "priority": "1",
            }
        )
        job_func = manual_orderpoint.run_replenishment
        self._set_qty_in_location(self.product, location_src, 20)
        with trap_jobs() as trap:
            out_move_2 = self._create_outgoing_move(2.0)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                job_func,
                args=(out_move_2.product_id,),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            trap.perform_enqueued_jobs()
        replenish_move = self._get_replenishment_move(manual_orderpoint)
        self.assertEqual(replenish_move, replenish_move_manual)

        self.assertEqual(replenish_move.product_uom_qty, move_qty + 2.0)

        # Check priority has been changed
        self.assertEqual("1", replenish_move.priority)

    def test_mixed_replenishment_priority_two_products(self):
        """
        Create a manual orderpoint with 'normal' priority

        Create moves that will generate replenishment (outgoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Update orderpoint priority to 'urgent'

        Refill available quantity in reserve location

        Create an outgoing move (no move should be created)

        Launch the replenishment

        Check that the replenishment move for the product 1 has been
        updated to 'urgent' and the one for product 2 is still 'normal'.
        The qty to replenish for product 1 should be updated according
        to the new outgoing move qty.

        """
        product_1 = self.product
        product_2 = self.env["product.product"].create(
            {
                "name": "Product 2",
                "type": "product",
            }
        )
        move_qty = 10

        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="manual",
            proc_run_async=False,
        )
        self._create_outgoing_move(move_qty)
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

        orderpoint.priority = "1"

        self.product = product_1
        self._set_qty_in_location(product_1, location_src, 20)
        # we use a date in the past to check that the resulting
        # replenishment move will be planned at the right date (i.e. the one of the
        #  new outgoing move) and the picking scheduled date is updated accordingly
        move_date = datetime.datetime(2023, 1, 1)
        self._create_outgoing_move(
            2.0, date=move_date
        )  # make sure the move is taken into account in replenishment

        orderpoint.run_replenishment()

        replenish_move = self._get_replenishment_move(orderpoint, product=product_1)
        replenish_move_2 = self._get_replenishment_move(orderpoint, product=product_2)

        self.assertEqual(replenish_move, replenish_move_manual_1)
        self.assertEqual(replenish_move.product_uom_qty, move_qty + 2.0)
        self.assertEqual(replenish_move.date, move_date)
        self.assertEqual(replenish_move.picking_id.scheduled_date, move_date)

        # Check priority has been changed (for both moves)
        self.assertEqual("1", replenish_move.priority)
        self.assertEqual("0", replenish_move_2.priority)

    def test_mixed_replenishment_priority_bis(self):
        """
        Create a manual orderpoint with 'normal' priority

        Create moves that will generate replenishment (outgoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Create a second orderpoint with 'urgent' priority

        Create moves that will generate replenishment (outgoing + quantity on Reserve).

        Run the second orderpoint for an other product

        Check the move is created

        Each moves must:
        - be linked to the correct orderpoint
        - have the correct priority

        The picking must have the highest priority between the 2 moves (i.e. 'urgent')

        """
        # we drop the unique constraint here because ideally we want to create orderpoints
        # for the same location with different priority
        self.env.cr.execute(
            """
            ALTER TABLE stock_location_orderpoint
            DROP CONSTRAINT stock_location_orderpoint_location_route_unique;
            """
        )
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
            proc_run_async=False,
        )
        self._create_outgoing_move(move_qty)
        self._create_incoming_move(move_qty, location_src)
        orderpoint.run_replenishment()
        replenish_move_1 = self._get_replenishment_move(orderpoint, product=product_1)

        orderpoint_2 = orderpoint.copy({"priority": "1"})
        self.product = product_2
        move_date = datetime.datetime(2023, 1, 1)
        self._create_outgoing_move(move_qty, product=product_2, date=move_date)
        self._create_incoming_move(move_qty, location_src, product=product_2)
        orderpoint_2.run_replenishment()
        replenish_move_2 = self._get_replenishment_move(orderpoint_2, product=product_2)

        self.assertTrue(replenish_move_1)
        self.assertTrue(replenish_move_2)

        self.assertEqual("0", replenish_move_1.priority)
        self.assertEqual("1", replenish_move_2.priority)
        self.assertEqual(move_date, replenish_move_2.date)
        self.assertEqual(replenish_move_1.picking_id, replenish_move_2.picking_id)
        self.assertEqual("1", replenish_move_1.picking_id.priority)
        self.assertEqual(move_date, replenish_move_2.picking_id.scheduled_date)

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

        # ↓ we drop the unique constraint here because ideally we want to create orderpoints
        # that have exactly the same characteristics except for the replenish_method (in order
        # to make sure the moves get merged)
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
            proc_run_async=False,
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

    def test_orderpoint_priority_reassignment_on_shared_replenishment(self):
        product = self.product
        self.env.cr.execute(
            """
                    ALTER TABLE stock_location_orderpoint
                    DROP CONSTRAINT stock_location_orderpoint_location_route_unique;
                    """
        )

        (orderpoint_1, replenish_loc_1,) = self._create_orderpoint_complete(
            "Reserve",
            trigger="manual",
            proc_run_async=False,
        )
        orderpoint_2 = orderpoint_1.copy({"priority": "1"})

        # Set inventory on replenishment locations
        for repl_loc in [replenish_loc_1]:
            self.env["stock.quant"].with_context(inventory_mode=True).create(
                {
                    "product_id": product.id,
                    "location_id": repl_loc.id,
                    "inventory_quantity": 50.0,
                }
            )._apply_inventory()

        out_move = self._create_outgoing_move(11, orderpoint_1.location_id, product)
        self._run_replenishment(orderpoint_1)
        out_move._action_cancel()

        replenish_move_1 = self._get_replenishment_move(orderpoint_1, product)
        self.assertEqual(replenish_move_1.product_uom_qty, 11.0)
        self.assertEqual(replenish_move_1.priority, "0")

        # Create a need that is already covered by the existing repl move
        self._create_outgoing_move(2, orderpoint_2.location_id, product)
        self._run_replenishment(orderpoint_2)
        replenish_move_2 = self._get_replenishment_move(orderpoint_2, product)
        self.assertEqual(replenish_move_1, replenish_move_2)
        self.assertEqual(replenish_move_2.priority, "1")
