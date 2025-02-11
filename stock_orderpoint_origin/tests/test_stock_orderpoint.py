from odoo.tests import common


class TestOrderpointPurchaseLink(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.PurchaseOrder = cls.env["purchase.order"]
        cls.PurchaseOrderLine = cls.env["purchase.order.line"]
        cls.StockLocation = cls.env["stock.location"]
        cls.StockRoute = cls.env["stock.route"]
        cls.StockWarehouse = cls.env["stock.warehouse"]
        cls.StockWarehouseOrderpoint = cls.env["stock.warehouse.orderpoint"]

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "John Odoo",
            }
        )
        cls.product = cls.env.ref("product.product_product_5")
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.stock_location_id = cls.warehouse.lot_stock_id.id

    def test_ao(self):
        # import wdb; wdb.set_trace()
        op = self.env["stock.warehouse.orderpoint"].create(
            {
                "name": self.product.name,
                "location_id": self.stock_location_id,
                "product_id": self.product.id,
                "product_min_qty": 1,
                "product_max_qty": 8,
                "qty_to_order": 3,
                "trigger": "manual",
            }
        )
        op.action_replenish()
        purchase_order_line = self.env["purchase.order.line"].search(
            [("product_id", "=", self.product.id)], order="id desc", limit=1
        )
        self.assertTrue(bool(purchase_order_line))
        purchase_order = purchase_order_line.order_id
        origin = purchase_order.origin
        self.assertIn(self.product.name, origin)
        sale_orders = purchase_order._get_sale_orders()
        self.assertIn(purchase_order.order_line.source_group_ids.sale_id, sale_orders)
        so_name = sale_orders.mapped("name")[0]
        self.assertIn(so_name, origin)
