# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import datetime

from freezegun import freeze_time

from odoo.fields import Date
from odoo.tools.date_utils import relativedelta

from odoo.addons.stock_average_daily_sale.tests.common import CommonAverageSaleTest
from odoo.addons.stock_location_orderpoint.tests.common import (
    TestLocationOrderpointCommon,
)


class TestOrderpointAverage(CommonAverageSaleTest, TestLocationOrderpointCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Remove existing orderpoints, create new locations as:
        # - Stock
        #   - Area 1
        #     - Shelf 1
        #   - Area 2
        #     - Shelf 2
        cls.now = Date.today()

        cls.env["stock.location.orderpoint"].search([]).unlink()
        cls.area_1 = cls.env["stock.location"].create(
            {
                "name": "Area 1",
                "location_id": cls.warehouse.lot_stock_id.id,
                "usage": "view",
            }
        )

        cls.shelf_1 = cls.env["stock.location"].create(
            {
                "name": "Shelf 1",
                "location_id": cls.area_1.id,
            }
        )
        cls.area_2 = cls.env["stock.location"].create(
            {
                "name": "Area 2",
                "location_id": cls.warehouse.lot_stock_id.id,
                "usage": "view",
            }
        )

        cls.shelf_2 = cls.env["stock.location"].create(
            {
                "name": "Shelf 2",
                "location_id": cls.area_2.id,
            }
        )
        # Create one orderpoint on each area
        cls.orderpoint_1, cls.replenish_1 = cls._create_orderpoint_complete(
            "Replenish Area 1",
            trigger="manual",
            replenish_method="average_daily_sale",
            location_dest=cls.area_1,
        )
        cls.orderpoint_2, cls.replenish_2 = cls._create_orderpoint_complete(
            "Replenish Area 2",
            trigger="manual",
            replenish_method="average_daily_sale",
            location_dest=cls.area_2,
        )
        cls.orderpoint_cron, cls.replenish_cron = cls._create_orderpoint_complete(
            "Replenish Cron",
            trigger="cron",
            replenish_method="average_daily_sale",
            location_dest=cls.area_1,
        )

        # create average daily sale
        # By default, products have abc_storage == 'b'
        # So, the averages should correspond to 'b' one
        #
        # Create four outgoing moves for the period of time of that abc classification
        # for product 1/Shelf 1, and one move for product 2/Shelf 2
        #
        # Refresh the report
        cls.inventory_date = Date.to_string(cls.now - relativedelta(cls.now, weeks=30))
        with freeze_time(cls.inventory_date):
            cls._set_qty_in_location(cls.product_1, cls.shelf_1, 50.0)
        with freeze_time(cls.inventory_date):
            cls._set_qty_in_location(cls.product_2, cls.shelf_2, 60.0)

        move_1_date = Date.to_string(cls.now - relativedelta(weeks=11))
        cls._create_outgoing_move(10.0, move_1_date, cls.shelf_1, cls.product_1)

        move_1_date = Date.to_string(cls.now - relativedelta(weeks=10))
        cls._create_outgoing_move(8.0, move_1_date, cls.shelf_1, cls.product_1)

        move_1_date = Date.to_string(cls.now - relativedelta(weeks=9))
        cls._create_outgoing_move(2.0, move_1_date, cls.shelf_1, cls.product_1)

        move_1_date = Date.to_string(cls.now - relativedelta(weeks=9))
        cls._create_outgoing_move(2.0, move_1_date, cls.shelf_1, cls.product_1)

        move_2_date = Date.to_string(cls.now - relativedelta(weeks=9))
        cls._create_outgoing_move(12.0, move_2_date, cls.shelf_2, cls.product_2)

        cls._refresh()

    @classmethod
    def _create_move(cls, name, qty, location, location_dest, product=None, **kwargs):
        product = product or cls.product
        uom = product.uom_id
        vals = {
            "name": name,
            "date": datetime.today(),
            "product_id": product.id,
            "product_uom": uom.id,
            "product_uom_qty": qty,
            "location_id": location.id,
            "location_dest_id": location_dest.id,
        }
        vals.update(kwargs)
        move = cls.env["stock.move"].create(vals)
        move._write({"create_date": datetime.now()})
        move._action_confirm()
        return move

    @classmethod
    def _create_outgoing_move(cls, qty, move_date, origin, product, done=True):
        with freeze_time(move_date):
            move = cls._create_move(
                "Shelf 1 > Customers",
                qty,
                origin,
                cls.customers,
                product,
                picking_type_id=cls.env.ref("stock.picking_type_out").id,
            )
            move._action_confirm()
            if done:
                move._action_assign()
                move._assign_picking()
                move.picking_id.priority = "1"
                move.quantity_done = move.product_uom_qty
                move._action_done()
        return move

    def setUp(self):
        super().setUp()

    def test_orderpoint_average(self):
        # Run the orderpoint
        #
        # Check there is a replenishment move with the missing quantity
        avg_product_1 = self.env["stock.average.daily.sale"].search(
            [("product_id", "=", self.product_1.id)]
        )
        self.assertTrue(avg_product_1)
        # Void inventory on Shelf 1
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": self.product_1.id,
                "location_id": self.shelf_1.id,
                "inventory_quantity": 0.0,
            }
        )._apply_inventory()

        # Set invnetory on replenishment locations
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": self.product_1.id,
                "location_id": self.replenish_1.id,
                "inventory_quantity": 50.0,
            }
        )._apply_inventory()

        self._create_outgoing_move(8, self.now, self.area_1, self.product_1, done=False)

        missing_quantity = (
            avg_product_1.recommended_qty
            + 8.0
            - self.product_1.with_context(location=self.shelf_1.id).virtual_available
        )

        self._run_replenishment(self.orderpoint_1)

        replenish_move = self._get_replenishment_move(self.orderpoint_1, self.product_1)
        self.assertTrue(replenish_move)
        self.assertEqual(19.0, replenish_move.product_uom_qty)

        self.assertEqual(missing_quantity, replenish_move.product_uom_qty)

    def test_orderpoint_average_less(self):
        avg_product_1 = self.env["stock.average.daily.sale"].search(
            [("product_id", "=", self.product_1.id)]
        )
        self.assertTrue(avg_product_1)
        # Void inventory on Shelf 1
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": self.product_1.id,
                "location_id": self.shelf_1.id,
                "inventory_quantity": 0.0,
            }
        )._apply_inventory()

        # Set invnetory on replenishment locations
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": self.product_1.id,
                "location_id": self.replenish_1.id,
                "inventory_quantity": 15.0,
            }
        )._apply_inventory()

        self._create_outgoing_move(8, self.now, self.area_1, self.product_1, done=False)

        self._run_replenishment(self.orderpoint_1)

        replenish_move = self._get_replenishment_move(self.orderpoint_1, self.product_1)
        self.assertTrue(replenish_move)
        self.assertEqual(15.0, replenish_move.product_uom_qty)

    def test_cron_replenish_location_under_recommended_qty(self):
        """Set qty in location less than the recommended qty.

        When the cron run, it should create a replenishment move.
        """
        avg_product_1 = self.env["stock.average.daily.sale"].search(
            [("product_id", "=", self.product_1.id)]
        )
        self.assertTrue(avg_product_1)
        self._set_qty_in_location(
            self.product_1, self.shelf_1, avg_product_1.recommended_qty - 1
        )

        # Set invnetory on replenishment locations
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": self.product_1.id,
                "location_id": self.replenish_cron.id,
                "inventory_quantity": 15.0,
            }
        )._apply_inventory()

        self._create_outgoing_move(8, self.now, self.area_1, self.product_1, done=False)
        self._run_replenishment(self.orderpoint_cron)
        replenish_move = self._get_replenishment_move(
            self.orderpoint_cron, self.product_1
        )
        self.assertTrue(replenish_move)
        self.assertEqual(9.0, replenish_move.product_uom_qty)
