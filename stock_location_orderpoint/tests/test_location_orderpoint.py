# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from contextlib import contextmanager
from unittest.mock import patch

import freezegun
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from odoo.addons.queue_job.job import identity_exact
from odoo.addons.queue_job.tests.common import trap_jobs

from .common import TestLocationOrderpointCommon


class TestLocationOrderpoint(TestLocationOrderpointCommon):
    def test_manual_replenishment(self):
        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2", trigger="manual"
        )
        orderpoint2, location_src2 = self._create_orderpoint_complete(
            "Stock2.2", trigger="manual"
        )

        self.assertEqual(orderpoint.location_src_id, location_src)
        move = self._create_outgoing_move(12)
        move = self._create_outgoing_move(1)
        self.assertEqual(move.state, "confirmed")

        orderpoints = orderpoint | orderpoint2
        self._run_replenishment(orderpoints)

        replenish_move = self._get_replenishment_move(orderpoints)
        self.assertFalse(replenish_move)

        self._create_quants(self.product, location_src, 12)

        self._run_replenishment(orderpoints)
        replenish_move = self._get_replenishment_move(orderpoints)
        self._assert_replenishment_move(replenish_move, 12, orderpoint)

        replenish_move._action_cancel()

        self._create_quants(self.product, location_src2, 12)
        self._run_replenishment(orderpoints)

        replenish_moves = self._get_replenishment_move(orderpoints)
        self.assertEqual(len(replenish_moves), 2)
        self.assertEqual(sum(replenish_moves.mapped("product_qty")), 13)

        move = replenish_moves.filtered(
            lambda _move: _move.rule_id == orderpoint.route_id.rule_ids
        )
        self._assert_replenishment_move(move, 12, orderpoint)

        move = replenish_moves - move
        self._assert_replenishment_move(move, 1, orderpoint2)

    @contextmanager
    def _freeze_time(self, now):
        with freezegun.freeze_time(now), patch.object(
            self.env.cr.__class__, "now", return_value=now
        ):
            yield

    def test_check_unique(self):
        orderpoint, location_src = self._create_orderpoint_complete("Stock2")
        with mute_logger("odoo.sql_db"):
            with self.assertRaises(IntegrityError):
                self._create_orderpoint(route_id=orderpoint.route_id)

    def test_check_constrains(self):
        with self.assertRaises(ValidationError):
            self._create_orderpoint(route_id=self.warehouse.delivery_route_id)

    def test_cron_replenishment(self):
        cron = self.env.ref("stock_location_orderpoint.ir_cron_location_replenishment")
        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2", trigger="cron"
        )
        # at this point the orderpoint has no last_cron_execution
        self.assertFalse(orderpoint.last_cron_execution)
        self._create_outgoing_move(12)

        # outgoing move but without available quantity -> no replenishment
        self.product.invalidate_recordset()
        now = fields.Datetime.now()
        with self._freeze_time(now):
            cron.method_direct_trigger()
        self.assertEqual(orderpoint.last_cron_execution, now)

        replenish_move = self._get_replenishment_move(orderpoint)
        self.assertFalse(replenish_move)

        # create the available quantity -> replenishment
        tomorrow = now.replace(day=now.day + 1)
        with self._freeze_time(tomorrow):
            self._set_qty_in_location(self.product, location_src, 12)

        self.product.invalidate_recordset()
        day_after_tomorrow = tomorrow.replace(day=tomorrow.day + 1)
        with self._freeze_time(day_after_tomorrow):
            cron.method_direct_trigger()

        replenish_move = self._get_replenishment_move(orderpoint)
        self._assert_replenishment_move(replenish_move, 12, orderpoint)
        self.assertEqual(orderpoint.last_cron_execution, day_after_tomorrow)

    def test_auto_replenishment(self):
        job_func = self.env["stock.location.orderpoint"].run_auto_replenishment
        move_qty = 12
        with trap_jobs() as trap:
            move = self._create_outgoing_move(move_qty)
            trap.assert_jobs_count(0, only=job_func)
            trap.perform_enqueued_jobs()
            replenish_move = self.env["stock.move"].search(
                [
                    ("product_id", "=", move.product_id.id),
                    ("location_dest_id", "=", move.location_id.id),
                ]
            )
            self.assertFalse(replenish_move)

        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2", trigger="auto"
        )
        with trap_jobs() as trap:
            move = self._create_outgoing_move(move_qty)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                orderpoint.browse([]).run_auto_replenishment,
                args=(move.product_id, move.location_id, "location_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            self.product.invalidate_recordset()
            trap.perform_enqueued_jobs()
            replenish_move = self._get_replenishment_move(orderpoint)
            self.assertFalse(replenish_move)

        with trap_jobs() as trap:
            move = self._create_incoming_move(move_qty, location_src)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                orderpoint.browse([]).run_auto_replenishment,
                args=(move.product_id, move.location_dest_id, "location_src_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            self.product.invalidate_recordset()
            trap.perform_enqueued_jobs()
            replenish_move = self._get_replenishment_move(orderpoint)
            self._assert_replenishment_move(replenish_move, move_qty, orderpoint)

        # Create a second incoming move so that the qty_available would be 24
        move = self._create_incoming_move(move_qty, location_src)
        with trap_jobs() as trap:
            move = self._create_outgoing_move(move_qty)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                orderpoint.browse([]).run_auto_replenishment,
                args=(move.product_id, move.location_id, "location_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            self.product.invalidate_recordset()
            trap.perform_enqueued_jobs()
            replenish_move_new = self._get_replenishment_move(orderpoint)
            self.assertEqual(replenish_move, replenish_move_new)
            self._assert_replenishment_move(replenish_move, move_qty * 2, orderpoint)

    def test_auto_replenishment_channel(self):
        """
        Check that the channel for enqueud job is
        root.stock_location_orderpoint_auto_replenishment
        """
        job_func = self.env["stock.location.orderpoint"].run_auto_replenishment
        move_qty = 12

        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2",
            trigger="auto",
        )
        with trap_jobs() as trap:
            move = self._create_outgoing_move(move_qty)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                orderpoint.browse([]).run_auto_replenishment,
                args=(move.product_id, move.location_id, "location_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            self.product.invalidate_recordset()
            trap.perform_enqueued_jobs()
            replenish_move = self._get_replenishment_move(orderpoint)
            self.assertFalse(replenish_move)

        with trap_jobs() as trap:
            move = self._create_incoming_move(move_qty, location_src)
            trap.assert_jobs_count(1, only=job_func)
            trap.assert_enqueued_job(
                orderpoint.browse([]).run_auto_replenishment,
                args=(move.product_id, move.location_dest_id, "location_src_id"),
                kwargs={},
                properties=dict(
                    identity_key=identity_exact,
                ),
            )
            job = trap.enqueued_jobs[0]
            self.assertEqual(
                job.channel, "root.stock_location_orderpoint_auto_replenishment"
            )

    def test_auto_no_replenishment(self):
        """
        Create a stock move that should not create a replenishment:
          - A move from a new stock location 'WH/Stock 2' to Scrap
        """
        job_func = self.env["stock.location.orderpoint"].run_auto_replenishment
        with trap_jobs() as trap:
            new_location = self.env["stock.location"].create(
                {
                    "name": "Other Stock",
                    "location_id": self.location_dest.location_id.id,
                }
            )
            _, _ = self._create_orderpoint_complete("Stock2", trigger="auto")
            self.location_dest = new_location
            self._create_quants(self.product, self.location_dest, 10.0)
            move = self._create_scrap_move(10.0, self.location_dest)
            trap.assert_jobs_count(0, only=job_func)
            trap.perform_enqueued_jobs()
            replenish_move = self.env["stock.move"].search(
                [
                    ("product_id", "=", move.product_id.id),
                    ("location_dest_id", "=", move.location_id.id),
                ]
            )
            self.assertFalse(replenish_move)

    def test_orderpoint_count(self):
        """
        One orderpoint has already been created in demo data.
        Check after each creation that count is increasing.
        """
        _, _ = self._create_orderpoint_complete("Stock2", trigger="cron")
        self.assertEqual(1, self.location_dest.location_orderpoint_count)
        _, _ = self._create_orderpoint_complete("Stock3", trigger="cron")
        self.assertEqual(2, self.location_dest.location_orderpoint_count)
