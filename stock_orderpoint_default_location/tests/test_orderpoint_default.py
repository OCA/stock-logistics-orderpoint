# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import Form, TransactionCase


class TestOrderPOintDefault(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.orderpoint_obj = cls.env["stock.warehouse.orderpoint"]
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product Test",
                "company_id": False,
            }
        )
        cls.company_2 = cls.env["res.company"].create({"name": "Company 2"})
        cls.warehouse_2 = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company_2.id)]
        )
        cls.different_stock = (
            cls.env["stock.location"]
            .with_company(cls.company_2)
            .create(
                {
                    "name": "Stock 2",
                    "location_id": cls.warehouse_2.view_location_id.id,
                }
            )
        )
        cls.warehouse_2.default_orderpoint_location_id = cls.different_stock

    def test_default_with_warehouse(self):
        # Create an orderpoint on the company 2 mentionning the warehouse
        with Form(self.orderpoint_obj.with_company(self.company_2)) as orderpoint_form:
            orderpoint_form.product_id = self.product
        orderpoint = orderpoint_form.save()
        self.assertEqual(orderpoint.location_id, self.different_stock)

    def test_default_with_warehouse_no_default(self):
        # No default location for warehouse
        self.warehouse_2.default_orderpoint_location_id = False
        # Create an orderpoint on the company 2 mentionning the warehouse
        with Form(self.orderpoint_obj.with_company(self.company_2)) as orderpoint_form:
            orderpoint_form.product_id = self.product
        orderpoint = orderpoint_form.save()
        self.assertEqual(orderpoint.location_id, self.warehouse_2.lot_stock_id)
