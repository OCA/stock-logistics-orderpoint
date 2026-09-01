# Copyright 2018-20 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestStockWarehouseOrderpoint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Refs
        cls.group_stock_manager = cls.env.ref("stock.group_stock_manager")
        cls.group_purchase_manager = cls.env.ref("purchase.group_purchase_manager")
        cls.group_change_procure_qty = cls.env.ref(
            "stock_orderpoint_manual_procurement." "group_change_orderpoint_procure_qty"
        )
        cls.company1 = cls.env.ref("base.main_company")

        # Get required Model
        cls.reordering_rule_model = cls.env["stock.warehouse.orderpoint"]
        cls.product_model = cls.env["product.product"]
        cls.purchase_model = cls.env["purchase.order"]
        cls.purchase_line_model = cls.env["purchase.order.line"]
        cls.user_model = cls.env["res.users"]
        cls.product_ctg_model = cls.env["product.category"]
        cls.stock_change_model = cls.env["stock.change.product.qty"]
        cls.make_procurement_orderpoint_model = cls.env["make.procurement.orderpoint"]

        # Create users
        cls.user = cls._create_user(
            "user_1",
            [
                cls.group_stock_manager,
                cls.group_change_procure_qty,
                cls.group_purchase_manager,
            ],
            cls.company1,
        )
        # Get required Model data
        cls.product_uom = cls.env.ref("uom.product_uom_unit")
        cls.location = cls.env.ref("stock.stock_location_stock")
        cls.dozen = cls.env.ref("uom.product_uom_dozen")

        # Create vendor and supplier info
        test_seller = cls.env["res.partner"].create({"name": "Test seller"})
        cls.vendor = cls.env["product.supplierinfo"].create(
            {"partner_id": test_seller.id, "price": 8.0}
        )

        # Create Product category and Product
        cls.product_ctg = cls._create_product_category()
        cls.product = cls._create_product()

        # Add default quantity
        quantity = 20.00
        cls._update_product_qty(cls.product, quantity)

        # Create Reordering Rule
        cls.reorder = cls.create_orderpoint()

    @classmethod
    def _create_user(cls, login, groups, company):
        """Create a user."""
        group_ids = [group.id for group in groups]
        user = cls.user_model.with_context(no_reset_password=True).create(
            {
                "name": "Test User",
                "login": login,
                "password": "demo",
                "email": "test@yourcompany.com",
                "company_id": company.id,
                "company_ids": [(4, company.id)],
                "groups_id": [(6, 0, group_ids)],
            }
        )
        return user

    @classmethod
    def _create_product_category(cls):
        """Create a Product Category."""
        product_ctg = cls.product_ctg_model.create({"name": "test_product_ctg"})
        return product_ctg

    @classmethod
    def _create_product(cls):
        """Create a Product."""
        product = cls.product_model.create(
            {
                "name": "Test Product",
                "categ_id": cls.product_ctg.id,
                "is_storable": True,
                "uom_id": cls.product_uom.id,
                "variant_seller_ids": [(6, 0, [cls.vendor.id])],
            }
        )
        return product

    @classmethod
    def _update_product_qty(cls, product, quantity):
        """Update Product quantity."""
        change_product_qty = cls.stock_change_model.create(
            {
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "new_quantity": quantity,
            }
        )
        change_product_qty.change_product_qty()
        return change_product_qty

    @classmethod
    def create_orderpoint(cls):
        """Create a Reordering Rule"""
        reorder = cls.reordering_rule_model.with_user(cls.user).create(
            {
                "name": "Order-point",
                "product_id": cls.product.id,
                "product_min_qty": 100.0,
                "product_max_qty": 500.0,
                "qty_multiple": 1.0,
                "procure_uom_id": cls.dozen.id,
            }
        )
        return reorder

    def create_orderpoint_procurement(self):
        """Make Procurement from Reordering Rule"""
        wizard = (
            self.make_procurement_orderpoint_model.with_user(self.user)
            .with_context(
                active_model="stock.warehouse.orderpoint",
                active_ids=self.reorder.ids,
                active_id=self.reorder.id,
            )
            .create({})
        )
        for line in wizard.item_ids:
            line.onchange_uom_id()
        wizard.make_procurement()
        return wizard

    def test_security(self):
        """Test Manual Procurement created from Order-Point"""

        # Create Manual Procurement from order-point procured quantity
        self.create_orderpoint_procurement()

        # As per route configuration, it will create Purchase order
        # Assert that Procurement is created with the desired quantity
        purchase = self.purchase_model.search([("origin", "ilike", self.reorder.name)])
        self.assertEqual(len(purchase), 1)
        purchase_line = self.purchase_line_model.search(
            [("orderpoint_id", "=", self.reorder.id), ("order_id", "=", purchase.id)]
        )
        self.assertEqual(len(purchase_line), 1)
        self.assertEqual(self.reorder.product_id.id, purchase_line.product_id.id)
        # it could be using an existing PO, thus there could be more origins.
        self.assertTrue(self.reorder.name in purchase.origin)
        self.assertNotEqual(
            self.reorder.procure_recommended_qty, purchase_line.product_qty
        )
        if self.reorder.procure_uom_id == self.reorder.product_id.uom_po_id:
            # Our PO unit of measure is also dozens (procure uom)
            self.assertEqual(purchase_line.product_qty, 40)
        else:
            # PO unit of measure is units, not the same as procure uom.
            self.assertEqual(purchase_line.product_qty, 480)
