# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from .common import TestLocationOrderpointCommon


class TestSubLocationOrderpoint(TestLocationOrderpointCommon):
    """
    This is a test suite in order to test location orderpoints
    that point out stock locations views and demands on sublocations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Initialize the different stock sublocations
        cls.location_shelf_A = cls.location_obj.create(
            {
                "name": "Shelf A",
                "location_id": cls.warehouse.lot_stock_id.id,
            }
        )
        cls.location_shelf_B = cls.location_obj.create(
            {
                "name": "Shelf B",
                "location_id": cls.warehouse.lot_stock_id.id,
            }
        )
        cls.location_shelf_C = cls.location_obj.create(
            {
                "name": "Shelf C",
                "location_id": cls.warehouse.lot_stock_id.id,
            }
        )

        # Initialize the different replenishment sublocations
        cls.location_replenishment_shelf_A = cls.location_obj.create(
            {
                "name": "Replenish Shelf A",
                "location_id": cls.stock_location_replenish.id,
            }
        )
        cls.location_replenishment_shelf_B = cls.location_obj.create(
            {
                "name": "Replenish Shelf B",
                "location_id": cls.stock_location_replenish.id,
            }
        )
        cls.location_replenishment_shelf_C = cls.location_obj.create(
            {
                "name": "Replenish Shelf C",
                "location_id": cls.stock_location_replenish.id,
            }
        )

    def test_sublocation(self):
        # Create a product A and put:
        # # 10.0 quantity in Shelf A
        # # 100.0 quantity in Replenishment Shelf A
        # Create a product B and put:
        # # 5.0 quantity in Shelf B
        # # 200.0 quantity in Shelf B
        self.stock_location_orderpoint.active = True
        self.product_A = self.product_obj.create(
            {"name": "Product A", "type": "product"}
        )
        self.product_B = self.product_obj.create(
            {"name": "Product B", "type": "product"}
        )
        self._create_quants(self.product_A, self.location_shelf_A, 10.0)
        self._create_quants(self.product_A, self.location_replenishment_shelf_A, 100.0)
        self._create_quants(self.product_B, self.location_shelf_B, 5.0)
        self._create_quants(self.product_B, self.location_replenishment_shelf_B, 200.0)
        self.product = self.product_A
        self._create_outgoing_move(12)
        self.product = self.product_B
        self._create_outgoing_move(7)

        self._run_replenishment(self.stock_location_orderpoint)

        # For product B - we should replenish for quantity 2
        replenish_move_B = self._get_replenishment_move(self.stock_location_orderpoint)
        self.assertTrue(replenish_move_B)
        self.assertEqual(2.0, replenish_move_B.product_uom_qty)
        # Origin location should be the particular replenishment sub location
        self.assertEqual(
            self.location_replenishment_shelf_B,
            replenish_move_B.move_line_ids.location_id,
        )

        self.product = self.product_A
        replenish_move_A = self._get_replenishment_move(self.stock_location_orderpoint)
        self.assertTrue(replenish_move_A)
        self.assertEqual(2.0, replenish_move_A.product_uom_qty)
        # Origin location should be the particular replenishment sub location
        self.assertEqual(
            self.location_replenishment_shelf_A,
            replenish_move_A.move_line_ids.location_id,
        )
