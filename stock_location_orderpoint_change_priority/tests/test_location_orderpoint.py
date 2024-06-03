# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo.addons.queue_job.job import identity_exact
from odoo.addons.queue_job.tests.common import trap_jobs
from odoo.addons.stock_location_orderpoint.tests.common import (
    TestLocationOrderpointCommon,
)


class TestLocationOrderpointPriority(TestLocationOrderpointCommon):
    def test_mixed_replenishment_priority(self):
        """
        Create a manual orderpoint with normal priority

        Create moves that will generate replenishment (ougoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Create an automatic orderpoint with Urgent priority

        Change the existing outgoing move quantity (with lower need)

        Create an outgoing move with the difference quantity (no move should be created)

        Check that the replenishment move priority has changed to Urgent.
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
        Create a manual orderpoint with normal priority

        Create moves that will generate replenishment (ougoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Create an automatic orderpoint with Urgent priority

        Change the existing outgoing move quantity (with lower need)

        Create an outgoing move with the difference quantity (no move should be created)

        Check that the replenishment move priority has changed to Urgent.
        """
        product_2 = self.env["product.product"].create(
            {
                "name": "Product 2",
                "type": "product",
            }
        )
        job_func = self.env["stock.location.orderpoint"].run_auto_replenishment
        move_qty = 12

        manual_orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="manual",
        )
        out_move = self._create_outgoing_move(move_qty)
        self._create_incoming_move(move_qty, location_src)
        product_1 = self.product
        self.product = product_2
        self._create_outgoing_move(move_qty, product=product_2)
        self._create_incoming_move(move_qty, location_src, product=product_2)
        manual_orderpoint.run_replenishment()
        replenish_move_manual_1 = self._get_replenishment_move(
            manual_orderpoint, product=product_1
        )
        replenish_move_manual_2 = self._get_replenishment_move(
            manual_orderpoint, product=product_2
        )

        self.assertTrue(replenish_move_manual_1)
        self.assertTrue(replenish_move_manual_2)
        # Change the outgoing quantity
        out_move.product_uom_qty = 6.0

        self.assertEqual(6.0, out_move.product_uom_qty)

        manual_orderpoint.update(
            {
                "trigger": "auto",
                "priority": "1",
            }
        )
        self.product = product_1
        with trap_jobs() as trap:
            out_move_3 = self._create_outgoing_move(2.0)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                manual_orderpoint.browse([]).run_auto_replenishment,
                args=(out_move_3.product_id, out_move_3.location_id, "location_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            trap.perform_enqueued_jobs()

        replenish_move = self._get_replenishment_move(manual_orderpoint)
        replenish_move_2 = self._get_replenishment_move(
            manual_orderpoint, product=product_2
        )
        self.assertEqual(replenish_move, replenish_move_manual_1)

        self.assertEqual(replenish_move.product_uom_qty, 12.0)

        # Check priority has been changed
        self.assertEqual("1", replenish_move.priority)
        self.assertEqual("0", replenish_move_2.priority)

    def test_mixed_replenishment_priority_two_products_manual(self):
        """
        Create a manual orderpoint with normal priority

        Create moves that will generate replenishment (ougoing + quantity on Reserve).

        Run the manual orderpoint

        Check the move is created

        Create an automatic orderpoint with Urgent priority

        Change the existing outgoing move quantity (with lower need)

        Create an outgoing move with the difference quantity (no move should be created)

        Check that the replenishment move priority has changed to Urgent.
        """
        product_2 = self.env["product.product"].create(
            {
                "name": "Product 2",
                "type": "product",
            }
        )
        move_qty = 12

        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="auto",
        )
        out_move = self._create_outgoing_move(move_qty)
        with trap_jobs() as trap:
            self._create_incoming_move(move_qty, location_src)
            trap.perform_enqueued_jobs()
        product_1 = self.product
        self.product = product_2
        self._create_outgoing_move(move_qty, product=product_2)
        with trap_jobs() as trap:
            self._create_incoming_move(move_qty, location_src, product=product_2)
            trap.perform_enqueued_jobs()
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

        orderpoint.update(
            {
                "trigger": "manual",
                "priority": "1",
            }
        )

        self.product = product_1
        self._create_outgoing_move(2.0)

        orderpoint.run_replenishment()

        replenish_move = self._get_replenishment_move(orderpoint)
        replenish_move_2 = self._get_replenishment_move(orderpoint, product=product_2)
        self.assertEqual(replenish_move, replenish_move_manual_1)

        self.assertEqual(replenish_move.product_uom_qty, 12.0)

        # Check priority has been changed

        # In this case, we update all existing replenishments as manual orderpoint
        # is 'product agnostic'.
        self.assertEqual("1", replenish_move.priority)
        self.assertEqual("1", replenish_move_2.priority)
