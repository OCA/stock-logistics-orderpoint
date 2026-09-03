# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from .common import TestLocationOrderpointCommon


class TestLocationProductOrderpoint(TestLocationOrderpointCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "Product 2",
                "type": "product",
            }
        )
        cls.location_dest_2 = cls.env["stock.location"].create(
            {
                "name": "Test Location 2",
                "location_id": cls.warehouse.lot_stock_id.id,
            }
        )
        cls.orderpoint, cls.location_src = cls._create_orderpoint_complete(
            "Reserve",
            trigger="manual",
            proc_run_async=False,
            location_dest=cls.location_dest,
        )
        cls.orderpoint_2, cls.location_src_2 = cls._create_orderpoint_complete(
            "Reserve 2",
            trigger="manual",
            proc_run_async=False,
            location_dest=cls.location_dest_2,
        )
        # create replenishment need for both products on both orderpoints as follows:
        # orderpoint 1:
        # - product 1: 10 units demand, 0 procurement
        # - product 2: 5 units demand, 5 procurement
        # orderpoint 2:
        # - product 1: 8 units demand, 3 procurement
        # - product 2: 12 units demand, 0 procurement
        # orderpoint 1:
        cls._create_outgoing_move(
            10,
            cls.location_dest,
            cls.product,
        )
        cls._create_outgoing_move(5, cls.location_dest, cls.product_2)
        cls._set_qty_in_location(cls.product_2, cls.location_src, 5)
        # orderpoint 2:
        cls._create_outgoing_move(8, cls.location_dest_2, cls.product)
        cls._create_outgoing_move(12, cls.location_dest_2, cls.product_2)
        cls._set_qty_in_location(cls.product, cls.location_src_2, 3)

        cls.StockLocationProductOrderpoint = cls.env[
            "stock.location.product.orderpoint"
        ]
        cls.StockLocationProductOrderpoint.search([]).unlink()

    def test_location_product_orderpoint_computation(self):
        """
        Test the computation of stock.location.product.orderpoint records for two
        orderpoints with two products.
        """
        self.StockLocationProductOrderpoint._generate_orderpoint_product_demand(
            self.orderpoint.id
        )
        self.StockLocationProductOrderpoint._generate_orderpoint_product_demand(
            self.orderpoint_2.id
        )

        # check orderpoint 1
        loc_prod_op_1 = self.StockLocationProductOrderpoint.search(
            [("stock_location_orderpoint_id", "=", self.orderpoint.id)]
        )
        self.assertEqual(len(loc_prod_op_1), 2)
        for loc_prod_op in loc_prod_op_1:
            if loc_prod_op.product_id == self.product:
                self.assertEqual(loc_prod_op.qty_demand, 10)
                self.assertEqual(loc_prod_op.qty_procurement, 0)
            elif loc_prod_op.product_id == self.product_2:
                self.assertEqual(loc_prod_op.qty_demand, 5)
                self.assertEqual(loc_prod_op.qty_procurement, 5)
            else:
                self.fail("Unexpected product in location product orderpoint")

        # check orderpoint 2
        loc_prod_op_2 = self.StockLocationProductOrderpoint.search(
            [("stock_location_orderpoint_id", "=", self.orderpoint_2.id)]
        )
        self.assertEqual(len(loc_prod_op_2), 2)
        for loc_prod_op in loc_prod_op_2:
            if loc_prod_op.product_id == self.product:
                self.assertEqual(loc_prod_op.qty_demand, 8)
                self.assertEqual(loc_prod_op.qty_procurement, 3)
            elif loc_prod_op.product_id == self.product_2:
                self.assertEqual(loc_prod_op.qty_demand, 12)
                self.assertEqual(loc_prod_op.qty_procurement, 0)
            else:
                self.fail("Unexpected product in location product orderpoint")

    def test_location_product_orderpoint_recomputation(self):
        """
        Test the recomputation of stock.location.product.orderpoint records when
        the demand changes.
        """
        # initial computation
        self.StockLocationProductOrderpoint._generate_orderpoint_product_demand(
            self.orderpoint.id
        )

        # change demand for product 1 on orderpoint 1
        self._create_outgoing_move(5, self.location_dest, self.product)

        # recompute
        self.StockLocationProductOrderpoint._generate_orderpoint_product_demand(
            self.orderpoint.id
        )

        # check that the demand for product 1 has changed to 15 and procurement is still 0
        loc_prod_op_1 = self.StockLocationProductOrderpoint.search(
            [
                ("stock_location_orderpoint_id", "=", self.orderpoint.id),
                ("product_id", "=", self.product.id),
            ]
        )
        self.assertEqual(len(loc_prod_op_1), 1)
        loc_prod_op = loc_prod_op_1[0]
        self.assertEqual(loc_prod_op.qty_demand, 15)
        self.assertEqual(loc_prod_op.qty_procurement, 0)
