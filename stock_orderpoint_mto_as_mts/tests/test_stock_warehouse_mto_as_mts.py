# Copyright 2024 Camptocamp SA
# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo.addons.base.tests.common import BaseCommon


class TestStockWareHouseMtoAsMts(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.warehouse1 = cls.env["stock.warehouse"].create(
            {
                "name": "Test Warehouse",
                "code": "TWH",
            }
        )

        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.mto_route.write(
            {
                "active": True,
                "is_mto": True,
            }
        )

    def test_archive_mto_rules_for_wh(self):
        self.mto_route.write({"rule_ids": False})
        mto_rule1, mto_rule2 = self.env["stock.rule"].create(
            [
                {
                    "name": "Rule 1",
                    "route_id": self.mto_route.id,
                    "location_dest_id": self.env.ref(
                        "stock.stock_location_customers"
                    ).id,
                    "location_src_id": self.warehouse.lot_stock_id.id,
                    "action": "pull",
                    "procure_method": "make_to_order",
                    "picking_type_id": self.warehouse.out_type_id.id,
                },
                {
                    "name": "Rule 2",
                    "route_id": self.mto_route.id,
                    "location_dest_id": self.env.ref(
                        "stock.stock_location_customers"
                    ).id,
                    "location_src_id": self.warehouse1.lot_stock_id.id,
                    "action": "pull",
                    "procure_method": "make_to_order",
                    "picking_type_id": self.warehouse1.out_type_id.id,
                },
            ]
        )
        self.assertEqual(len(self.mto_route.rule_ids), 2)
        # Enable mto_as_mts in warehouse0
        self.warehouse.write({"mto_as_mts": True})
        self.assertEqual(len(self.mto_route.rule_ids), 1)
        self.assertFalse(mto_rule1.active)
        self.assertTrue(mto_rule2.active)
