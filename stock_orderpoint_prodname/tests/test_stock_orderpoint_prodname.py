# © 2026 Solvos Consultoría Informática (<http://www.solvos.es>)
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo.addons.base.tests.common import BaseCommon


class TestStockOrderpointProdname(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_with_code = cls.env["product.product"].create(
            {
                "name": "Product With Code",
                "is_storable": True,
                "default_code": "TEST-CODE",
            }
        )
        cls.product_without_code = cls.env["product.product"].create(
            {
                "name": "Product Without Code",
                "is_storable": True,
            }
        )

    def test_orderpoint_name_uses_default_code(self):
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {"product_id": self.product_with_code.id}
        )
        self.assertEqual(orderpoint.name, self.product_with_code.default_code)

    def test_orderpoint_name_falls_back_to_product_name(self):
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {"product_id": self.product_without_code.id}
        )
        self.assertEqual(orderpoint.name, self.product_without_code.name)
