# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.fields import Command
from odoo.tests.common import new_test_user

from odoo.addons.base.tests.common import BaseCommon


class XYZClassificationCase(BaseCommon):
    """Levels and products, without any replenishment machinery."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Level = cls.env["xyz.classification.level"]
        cls.ProductLevel = cls.env["xyz.classification.product.level"]
        cls.company_bis = cls.env["res.company"].create({"name": "XYZ Company bis"})
        cls.env.user.company_ids = [Command.link(cls.company_bis.id)]
        cls.level_a, cls.level_b = cls.Level.create(
            [
                {"name": "a", "sequence": 1},
                {"name": "b", "sequence": 2},
            ]
        )
        cls.level_bis_a = cls.Level.create(
            {"name": "a", "sequence": 1, "company_id": cls.company_bis.id}
        )
        cls.own_levels = cls.level_a + cls.level_b + cls.level_bis_a
        # Record rules do not apply to the superuser, so company isolation is
        # checked through a real user.
        cls.user_bis = new_test_user(
            cls.env,
            login="xyz-user-bis",
            groups="base.group_user,stock.group_stock_manager",
            company_id=cls.company_bis.id,
            company_ids=[Command.set(cls.company_bis.ids)],
        )
        cls.size_attr = cls.env["product.attribute"].create(
            {
                "name": "Size",
                "create_variant": "no_variant",
                "value_ids": [
                    Command.create({"name": "S"}),
                    Command.create({"name": "M"}),
                ],
            }
        )
        cls.size_attr_value_m = cls.size_attr.value_ids[1]
        # company_id is set explicitly: product_company_default would otherwise
        # give the product a company and it would not be shared at all.
        cls.product_template = cls.env["product.template"].create(
            {
                "name": "Test sized",
                "company_id": False,
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": cls.size_attr.id,
                            "value_ids": [Command.set(cls.size_attr.value_ids.ids)],
                        }
                    )
                ],
            }
        )
        cls.product_product = cls.product_template.product_variant_ids
        cls.product_in_bis = cls.env["product.product"].create(
            {"name": "Owned by bis", "company_id": cls.company_bis.id}
        )

    def _offered_levels(self, product_level):
        """The levels on offer, restricted to the ones this case created, so
        that a database with levels of its own does not fail the comparison."""
        return product_level.allowed_level_ids._origin & self.own_levels

    @classmethod
    def _create_variant(cls, size_value):
        return cls.env["product.product"].create(
            {
                "product_tmpl_id": cls.product_template.id,
                "product_template_attribute_value_ids": [
                    Command.set(
                        size_value.pav_attribute_line_ids.product_template_value_ids.ids
                    )
                ],
            }
        )


class XYZFrequencyCase(XYZClassificationCase):
    """The above, plus a warehouse able to actually replenish something."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.StockRule = cls.env["stock.rule"]
        cls.Orderpoint = cls.env["stock.warehouse.orderpoint"]
        cls.Quant = cls.env["stock.quant"]
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        # A pull rule feeding stock from the supplier location, so that a
        # procurement produces a move without depending on purchase.
        cls.route = cls.env["stock.route"].create(
            {
                "name": "Test XYZ replenishment",
                "product_selectable": True,
                "company_id": cls.env.company.id,
            }
        )
        cls.StockRule.create(
            {
                "name": "Test XYZ supply rule",
                "action": "pull",
                "route_id": cls.route.id,
                "location_src_id": cls.supplier_location.id,
                "location_dest_id": cls.stock_location.id,
                "picking_type_id": cls.warehouse.in_type_id.id,
                "procure_method": "make_to_stock",
                "warehouse_id": cls.warehouse.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.level_x, cls.level_z = cls.Level.create(
            [
                {"name": "X", "sequence": 10, "replenishment_interval_days": 1},
                {"name": "Z", "sequence": 30, "replenishment_interval_days": 30},
            ]
        )
        cls.product_z = cls._create_product("Test Z mover")
        cls.orderpoint_z = cls._create_orderpoint(cls.product_z)
        cls.level_product_z = cls.ProductLevel.create(
            {"product_id": cls.product_z.id, "level_id": cls.level_z.id}
        )

    @classmethod
    def _create_product(cls, name):
        return cls.env["product.product"].create(
            {
                "name": name,
                "is_storable": True,
                "route_ids": [Command.set(cls.route.ids)],
            }
        )

    @classmethod
    def _create_orderpoint(cls, product):
        return cls.Orderpoint.create(
            {
                "warehouse_id": cls.warehouse.id,
                "location_id": cls.stock_location.id,
                "product_id": product.id,
                "product_min_qty": 2.0,
                "product_max_qty": 4.0,
                "trigger": "auto",
                "route_id": cls.route.id,
            }
        )

    def _scheduled_orderpoints(self, company_id=False):
        """The orderpoints the daily scheduler would consider right now."""
        return self.Orderpoint.search(
            self.StockRule._get_orderpoint_domain(company_id=company_id)
        )

    def _incoming_moves(self, product):
        return self.env["stock.move"].search(
            [
                ("product_id", "=", product.id),
                ("location_id", "=", self.supplier_location.id),
            ]
        )

    def _consume(self, product, quantity):
        """Register an outgoing demand, so that the forecast drops."""
        move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": quantity,
                "product_uom": product.uom_id.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
            }
        )
        move._action_confirm()
        return move
