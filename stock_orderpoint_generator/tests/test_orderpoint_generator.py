# Copyright 2016 Cyril Gaudin (Camptocamp)
# Copyright 2019 David Vidal - Tecnativa
# Copyright 2020 Víctor Martínez - Tecnativa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import Command, models
from odoo.exceptions import UserError

from odoo.addons.base.tests.common import BaseCommon


class TestOrderpointGenerator(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def make_move(product, qty, location, location_dest, date):
            move = cls.env["stock.move"].create(
                {
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": qty,
                    "location_id": location.id,
                    "location_dest_id": location_dest.id,
                    "date": date,
                }
            )
            move._action_confirm()
            move._action_assign()
            move.picked = True
            move._action_done()
            move.date = date
            move.move_line_ids.date = date
            return move

        cls.wizard_model = cls.env["stock.warehouse.orderpoint.generator"]
        cls.orderpoint_model = cls.env["stock.warehouse.orderpoint"]
        cls.orderpoint_template_model = cls.env["stock.warehouse.orderpoint.template"]
        cls.product_model = cls.env["product.product"]
        cls.quant_model = cls.env["stock.quant"]
        cls.p1 = cls.product_model.create(
            {"name": "Unittest P1", "type": "consu", "is_storable": True}
        )
        cls.p2 = cls.product_model.create(
            {"name": "Unittest P2", "type": "consu", "is_storable": True}
        )
        attribute = cls.env["product.attribute"].create(
            {"name": "Unittest attribute", "create_variant": "always"}
        )
        attribute_values = cls.env["product.attribute.value"].create(
            [
                {"name": "Unittest value 1", "attribute_id": attribute.id},
                {"name": "Unittest value 2", "attribute_id": attribute.id},
            ]
        )
        cls.multi_variant_tmpl = cls.env["product.template"].create(
            {
                "name": "Unittest multi variant",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [Command.set(attribute_values.ids)],
                        }
                    )
                ],
            }
        )
        cls.uom_box_10 = cls.env["uom.uom"].create(
            {
                "name": "Unittest box of 10",
                "relative_factor": 10.0,
                "relative_uom_id": cls.p1.uom_id.id,
            }
        )
        cls.wh1 = cls.env["stock.warehouse"].create(
            {"name": "TEST WH1", "code": "TST1"}
        )
        cls.stock_loc = cls.wh1.lot_stock_id
        location_obj = cls.env["stock.location"]
        cls.supplier_loc = location_obj.create(
            {"name": "Test supplier location", "usage": "supplier"}
        )
        cls.customer_loc = location_obj.create(
            {"name": "Test customer location", "usage": "customer"}
        )
        cls.orderpoint_fields_dict = {
            "warehouse_id": cls.wh1.id,
            "location_id": cls.wh1.lot_stock_id.id,
            "name": "TEST-ORDERPOINT-001",
            "product_max_qty": 15.0,
            "product_min_qty": 5.0,
            "replenishment_uom_id": cls.uom_box_10.id,
        }
        cls.template = cls.orderpoint_template_model.create(cls.orderpoint_fields_dict)

        # Create some moves for p1 and p2 so we can have a history to test
        # p1 stock history: [100, 50, 45, 55, 52]
        # p2 stock history: [1000, 950, 943, 1043, 1040]

        # t1 - p1 initial stock 100
        cls.quant_model._update_available_quantity(
            cls.p1, cls.stock_loc, 100, in_date="2019-01-01 01:00:00"
        )
        # t2 - p1 - stock.move location1 -50 # 50
        make_move(cls.p1, 50, cls.stock_loc, cls.customer_loc, "2019-01-01 02:00:00")
        # t3 - p1 - stock.move location1 -5 # 45
        make_move(cls.p1, 5, cls.stock_loc, cls.customer_loc, "2019-01-01 03:00:00")
        # t4 - p1 - stock.move location1 10 # 55
        make_move(cls.p1, 10, cls.supplier_loc, cls.stock_loc, "2019-01-01 04:00:00")
        # t5 - p1 - stock.move location1 -3 # 52
        make_move(cls.p1, 3, cls.stock_loc, cls.customer_loc, "2019-01-01 05:00:00")

        # t1 - p2 initial stock 1000
        cls.quant_model._update_available_quantity(
            cls.p2, cls.stock_loc, 1000, in_date="2019-01-01 01:00:00"
        )
        # t2 - p2 - stock.move location1 -50 # 950
        make_move(cls.p2, 50, cls.stock_loc, cls.customer_loc, "2019-01-01 02:00:00")
        # t3 - p2 - stock.move location1 -7 # 943
        make_move(cls.p2, 7, cls.stock_loc, cls.customer_loc, "2019-01-01 03:00:00")
        # t4 - p2 - stock.move location1 100 # 1043
        make_move(cls.p2, 100, cls.supplier_loc, cls.stock_loc, "2019-01-01 04:00:00")
        # t5 - p2 - stock.move location1 -3 # 1040
        make_move(cls.p2, 3, cls.stock_loc, cls.customer_loc, "2019-01-01 05:00:00")

    def check_orderpoint(self, products, template, expected_op_vals):
        orderpoints = self.orderpoint_model.search(
            [("name", "=", template.name)], order="product_id"
        )
        self.assertEqual(len(products), len(orderpoints))
        for i, product in enumerate(products):
            self.assertEqual(product, orderpoints[i].product_id)
        for orderpoint in orderpoints:
            for field in expected_op_vals.keys():
                op_field_value = orderpoint[field]
                if isinstance(orderpoint[field], models.Model):
                    op_field_value = orderpoint[field].id
                self.assertEqual(op_field_value, expected_op_vals[field])
        return orderpoints

    def wizard_over_products(self, product, template):
        return self.wizard_model.with_context(
            active_model=product._name,
            active_ids=product.ids,
        ).create({"orderpoint_template_id": [(6, 0, template.ids)]})

    def test_product_orderpoint(self):
        products = self.p1 + self.p2
        wizard = self.wizard_over_products(products, self.template)
        wizard.action_configure()
        self.check_orderpoint(products, self.template, self.orderpoint_fields_dict)

    def test_template_orderpoint(self):
        prod_tmpl = self.p1.product_tmpl_id + self.p2.product_tmpl_id
        wizard = self.wizard_over_products(prod_tmpl, self.template)
        wizard.action_configure()
        products = self.p1 + self.p2
        self.check_orderpoint(products, self.template, self.orderpoint_fields_dict)

    def test_template_variants_orderpoint(self):
        """Raise error if product has multiple variants"""
        self.assertGreater(len(self.multi_variant_tmpl.product_variant_ids), 1)
        wizard = self.wizard_over_products(self.multi_variant_tmpl, self.template)
        with self.assertRaises(UserError):
            wizard.action_configure()

    def test_auto_qty(self):
        """Compute min and max qty  according to criteria"""
        # p1 stock history: [100, 50, 45, 55, 52]

        # Max stock for p1: 100
        self.template.write(
            {
                "auto_min_qty": True,
                "auto_min_date_start": "2019-01-01 01:30:00",
                "auto_min_date_end": "2019-02-01 00:00:00",
                "auto_min_qty_criteria": "max",
            }
        )
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals = self.orderpoint_fields_dict.copy()
        del expected_op_vals["product_max_qty"]
        expected_op_vals.update({"product_min_qty": 100})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # Min stock for p1: 45
        self.template.write({"auto_min_qty_criteria": "min"})
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_min_qty": 45})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # Median stock for p1: 52
        self.template.write({"auto_min_qty_criteria": "median"})
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_min_qty": 52})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # Average stock for p1: 60.4
        self.template.write({"auto_min_qty_criteria": "avg"})
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_min_qty": 60.4})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # auto_max_qty with max value (100) and auto_min_qty with avg value (60.4)
        self.template.write(
            {
                "auto_max_qty": True,
                "auto_max_date_start": "2019-01-01 00:00:00",
                "auto_max_date_end": "2019-02-01 00:00:00",
                "auto_max_qty_criteria": "max",
            }
        )
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_max_qty": 100})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # Both auto_max_qty and auto_min_qty with max value
        self.template.write({"auto_min_qty_criteria": "max"})
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_min_qty": 100})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # Auto min and max over a shorter period
        self.template.write(
            {
                # Stock history for min date range: [50, 45, 55]
                "auto_min_date_start": "2019-01-01 02:30:00",
                "auto_min_date_end": "2019-01-01 04:30:00",
                "auto_min_qty_criteria": "avg",
                # Stock history for max date range: [45, 55, 52]
                "auto_max_date_start": "2019-01-01 03:30:00",
                "auto_max_date_end": "2019-01-01 05:30:00",
                "auto_max_qty_criteria": "max",
            }
        )
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_min_qty": 50, "product_max_qty": 55})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

        # Check delivered quantities
        self.template.write(
            {
                # Stock move history for min date range [-50, -5, 10]
                "auto_min_date_start": "2019-01-01 00:00:00",
                "auto_min_date_end": "2019-01-01 04:30:00",
                "auto_min_qty_criteria": "delivered",
                # Stock move history for max date range [-50, -5, 10, -3]
                "auto_max_date_start": "2019-01-01 00:00:00",
                "auto_max_date_end": "2019-02-01 00:00:00",
                "auto_max_qty_criteria": "delivered",
            }
        )
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals.update({"product_min_qty": 55, "product_max_qty": 58})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

    def test_auto_qty_multi_products(self):
        """Each product has a different history"""
        products = self.p1 + self.p2
        self.template.write(
            {
                "auto_min_qty": True,
                "auto_min_date_start": "2019-01-01 00:00:00",
                "auto_min_date_end": "2019-02-01 00:00:00",
                "auto_min_qty_criteria": "max",
            }
        )
        wizard = self.wizard_over_products(products, self.template)
        wizard.action_configure()
        expected_op_vals = self.orderpoint_fields_dict.copy()
        del expected_op_vals["product_min_qty"]
        del expected_op_vals["product_max_qty"]
        orderpoints = self.check_orderpoint(products, self.template, expected_op_vals)
        self.assertEqual(orderpoints[0].product_min_qty, 100)
        self.assertEqual(orderpoints[1].product_min_qty, 1043)

    def test_max_greater_than_auto_min(self):
        """Max qty must be greater than auto min qty"""

        # p1 stock history: [100, 50, 45, 55, 52]
        self.template.write(
            {
                "auto_min_qty": True,
                "auto_min_date_start": "2019-01-01 01:30:00",
                "auto_min_date_end": "2019-02-01 00:00:00",
                "auto_min_qty_criteria": "max",
                "product_max_qty": 15,
            }
        )
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals = self.orderpoint_fields_dict.copy()
        expected_op_vals.update({"product_min_qty": 100, "product_max_qty": 100})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)

    def test_min_lower_than_auto_max(self):
        """Min qty must be lower than auto Max qty"""

        # p1 stock history: [100, 50, 45, 55, 52]
        self.template.write(
            {
                "auto_max_qty": True,
                "auto_max_date_start": "2019-01-01 01:30:00",
                "auto_max_date_end": "2019-02-01 00:00:00",
                "auto_max_qty_criteria": "min",
                "product_min_qty": 150,
            }
        )
        wizard = self.wizard_over_products(self.p1, self.template)
        wizard.action_configure()
        expected_op_vals = self.orderpoint_fields_dict.copy()
        expected_op_vals.update({"product_min_qty": 45, "product_max_qty": 45})
        self.check_orderpoint(self.p1, self.template, expected_op_vals)
