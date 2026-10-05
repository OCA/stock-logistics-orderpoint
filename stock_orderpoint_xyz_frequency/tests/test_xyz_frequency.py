# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .common import XYZFrequencyCase


@tagged("post_install", "-at_install")
class TestXYZFrequency(XYZFrequencyCase):
    @mute_logger("odoo.sql_db")
    def test_interval_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            self.Level.create({"name": "Broken", "replenishment_interval_days": 0})

    def test_default_interval_is_daily(self):
        self.assertEqual(
            self.Level.create({"name": "Y"}).replenishment_interval_days, 1
        )

    def test_the_window_gates_the_scheduler(self):
        today = fields.Date.context_today(self.level_product_z)
        self.assertFalse(self.level_product_z.next_replenishment_date)
        self.assertIn(self.orderpoint_z, self._scheduled_orderpoints())
        self.level_product_z.next_replenishment_date = today + timedelta(days=5)
        self.assertNotIn(self.orderpoint_z, self._scheduled_orderpoints())
        self.level_product_z.next_replenishment_date = today
        self.assertIn(self.orderpoint_z, self._scheduled_orderpoints())
        self.level_product_z.next_replenishment_date = today - timedelta(days=1)
        self.assertIn(self.orderpoint_z, self._scheduled_orderpoints())

    def test_countdown_follows_the_window(self):
        today = fields.Date.context_today(self.level_product_z)
        self.assertEqual(self.level_product_z.days_to_next_replenishment, 0)
        self.level_product_z.next_replenishment_date = today + timedelta(days=5)
        self.assertEqual(self.level_product_z.days_to_next_replenishment, 5)
        # An elapsed window is not a negative countdown: the product is due.
        self.level_product_z.next_replenishment_date = today - timedelta(days=3)
        self.assertEqual(self.level_product_z.days_to_next_replenishment, 0)

    def test_unclassified_product_is_never_skipped(self):
        """Products with no XYZ level at all keep being replenished daily,
        which is why the module seeds no classification."""
        product = self._create_product("Test unclassified")
        orderpoint = self._create_orderpoint(product)
        self.level_product_z.next_replenishment_date = fields.Date.context_today(
            self.level_product_z
        ) + timedelta(days=5)
        scheduled = self._scheduled_orderpoints()
        self.assertIn(orderpoint, scheduled)
        self.assertNotIn(self.orderpoint_z, scheduled)

    def test_scheduler_stamps_the_window(self):
        today = fields.Date.context_today(self.level_product_z)
        self.StockRule._run_scheduler_tasks()
        self.assertEqual(self.level_product_z.last_replenishment_date, today)
        self.assertEqual(
            self.level_product_z.next_replenishment_date, today + timedelta(days=30)
        )
        self.assertNotIn(self.orderpoint_z, self._scheduled_orderpoints())

    def test_an_archived_level_classifies_nothing(self):
        """Archiving a level gives its products back the standard behaviour:
        considered on every run, and their frozen dates left alone."""
        today = fields.Date.context_today(self.level_product_z)
        self.level_product_z.next_replenishment_date = today + timedelta(days=5)
        self.level_z.active = False
        self.assertFalse(self.level_product_z.active)
        self.assertIn(self.orderpoint_z, self._scheduled_orderpoints())
        self.StockRule._run_scheduler_tasks()
        self.assertFalse(self.level_product_z.last_replenishment_date)
        self.assertEqual(
            self.level_product_z.next_replenishment_date, today + timedelta(days=5)
        )
        # Unarchiving the level does not classify the products again: the
        # classifications have to be unarchived themselves.
        self.level_z.active = True
        self.assertIn(self.orderpoint_z, self._scheduled_orderpoints())
        self.level_product_z.active = True
        self.assertNotIn(self.orderpoint_z, self._scheduled_orderpoints())

    def test_scheduler_ignores_products_without_orderpoint(self):
        product = self._create_product("Test no orderpoint")
        level = self.ProductLevel.create(
            {"product_id": product.id, "level_id": self.level_z.id}
        )
        self.StockRule._run_scheduler_tasks()
        self.assertFalse(level.last_replenishment_date)
        self.assertFalse(level.next_replenishment_date)

    def test_manual_replenishment_is_never_blocked(self):
        self.level_product_z.next_replenishment_date = fields.Date.context_today(
            self.level_product_z
        ) + timedelta(days=5)
        self.orderpoint_z.action_replenish()
        self.assertTrue(self._incoming_moves(self.product_z))

    def test_demand_accumulates_between_two_windows(self):
        """The point of the whole module: a Z product is looked at once, left
        alone while its demand piles up, and replenished in one go."""
        today = fields.Date.context_today(self.level_product_z)
        self.Quant._update_available_quantity(self.product_z, self.stock_location, 4.0)

        # Day 1: stock is at the maximum, nothing to order, but the product has
        # been considered so its window closes.
        self.StockRule._run_scheduler_tasks()
        self.assertFalse(self._incoming_moves(self.product_z))
        self.assertEqual(
            self.level_product_z.next_replenishment_date, today + timedelta(days=30)
        )

        # Days 5 to 25: the demand drags the forecast below zero. Without the
        # cadence each of these would have triggered its own small order.
        self._consume(self.product_z, 3.0)
        self._consume(self.product_z, 3.0)
        self._consume(self.product_z, 4.0)
        self.orderpoint_z.invalidate_recordset()
        self.assertEqual(self.orderpoint_z.qty_to_order, 10.0)

        self.StockRule._run_scheduler_tasks()
        self.assertFalse(self._incoming_moves(self.product_z))

        # Day 31: one order for everything that piled up.
        self.level_product_z.next_replenishment_date = today
        self.StockRule._run_scheduler_tasks()
        moves = self._incoming_moves(self.product_z)
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.product_uom_qty, 10.0)

    def test_reset_leaves_the_other_levels_alone(self):
        """Resetting is per level: it follows a change of that level's
        interval, and must not make the whole catalogue due at once."""
        product = self._create_product("Test X mover")
        self._create_orderpoint(product)
        level_product_x = self.ProductLevel.create(
            {"product_id": product.id, "level_id": self.level_x.id}
        )
        tomorrow = fields.Date.context_today(level_product_x) + timedelta(days=1)
        (self.level_product_z + level_product_x).write(
            {"next_replenishment_date": tomorrow}
        )
        self.level_z.action_reset_replenishment_windows()
        self.assertFalse(self.level_product_z.next_replenishment_date)
        self.assertIn(self.orderpoint_z, self._scheduled_orderpoints())
        self.assertEqual(level_product_x.next_replenishment_date, tomorrow)


@tagged("post_install", "-at_install")
class TestXYZFrequencyMultiCompany(XYZFrequencyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse_b = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company_bis.id)], limit=1
        )
        # Each company runs its own policy: the main one spaces this product
        # out over 30 days, the second one replenishes it every day.
        cls.level_x_b = cls.Level.create(
            {
                "name": "X",
                "sequence": 10,
                "replenishment_interval_days": 1,
                "company_id": cls.company_bis.id,
            }
        )
        cls.shared_product = cls.env["product.product"].create(
            {
                "name": "Test shared mover",
                "is_storable": True,
                "company_id": False,
                "route_ids": [Command.set(cls.route.ids)],
            }
        )
        cls.orderpoint_a = cls._create_orderpoint(cls.shared_product)
        cls.orderpoint_b = cls.Orderpoint.with_company(cls.company_bis).create(
            {
                "warehouse_id": cls.warehouse_b.id,
                "location_id": cls.warehouse_b.lot_stock_id.id,
                "product_id": cls.shared_product.id,
                "product_min_qty": 2.0,
                "product_max_qty": 4.0,
                "trigger": "auto",
            }
        )
        cls.level_shared_a = cls.ProductLevel.create(
            {"product_id": cls.shared_product.id, "level_id": cls.level_z.id}
        )

    def test_a_shared_product_carries_one_cadence_per_company(self):
        level_shared_b = self.ProductLevel.create(
            {"product_id": self.shared_product.id, "level_id": self.level_x_b.id}
        )
        self.assertEqual(level_shared_b.company_id, self.company_bis)
        today = fields.Date.context_today(self.level_shared_a)
        self.level_shared_a.next_replenishment_date = today + timedelta(days=5)
        level_shared_b.next_replenishment_date = today + timedelta(days=5)
        scheduled = self._scheduled_orderpoints()
        self.assertNotIn(self.orderpoint_a, scheduled)
        self.assertNotIn(self.orderpoint_b, scheduled)
        # company B reopens its own window without touching the other one
        level_shared_b.next_replenishment_date = False
        scheduled = self._scheduled_orderpoints()
        self.assertNotIn(self.orderpoint_a, scheduled)
        self.assertIn(self.orderpoint_b, scheduled)

    def test_each_company_stamps_its_own_interval(self):
        level_shared_b = self.ProductLevel.create(
            {"product_id": self.shared_product.id, "level_id": self.level_x_b.id}
        )
        today = fields.Date.context_today(self.level_shared_a)
        self.StockRule._run_scheduler_tasks()
        self.assertEqual(
            self.level_shared_a.next_replenishment_date, today + timedelta(days=30)
        )
        self.assertEqual(
            level_shared_b.next_replenishment_date, today + timedelta(days=1)
        )

    def test_scheduler_run_for_one_company_ignores_the_other(self):
        self.level_shared_a.next_replenishment_date = False
        self.StockRule._run_scheduler_tasks(company_id=self.company_bis.id)
        self.assertFalse(self.level_shared_a.last_replenishment_date)
