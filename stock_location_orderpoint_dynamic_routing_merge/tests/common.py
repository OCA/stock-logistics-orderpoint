# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.fields import Command
from odoo.tests import Form

from odoo.addons.stock_location_orderpoint.models.stock_location_orderpoint import (
    StockLocationOrderpoint,
)


class StockOrderpointDynamicMergeCommon:
    """
            Create a Stock structure like:

                            WH
                        //      \\
                Reserve (view)      Stock
                    ||
                Reserve Food

            Create a location orderpoint on Reserve => Stock
            Create a picking type from Reserve => Stock
            Create a picking type 'Picking Food' to replenish Stock from
            Reserve Food.
            Create a Dynamic Routing from Reserve To Reserve Food
        """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["stock.location.orderpoint"].search([]).write({"active": False})
        cls.location_obj = cls.env["stock.location"]
        cls.customers = cls.env.ref("stock.stock_location_customers")
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.wh = cls.env.ref("stock.stock_location_locations")
        cls.stock = cls.env.ref("stock.stock_location_stock")
        cls.location_stock_reserve = cls.location_obj.create(
            {
                "name": "Reserve",
                "location_id": cls.wh.id,
            }
        )
        cls.location_stock_reserve_food = cls.location_obj.create(
            {
                "name": "Food",
                "location_id": cls.location_stock_reserve.id,
            }
        )
        cls.pick_type_reserve = cls.env["stock.picking.type"].create(
            {
                "name": "Reserve",
                "code": "internal",
                "sequence_code": "RES",
                "warehouse_id": cls.wh.id,
                "use_create_lots": False,
                "use_existing_lots": True,
                "default_location_src_id": cls.location_stock_reserve.id,
                "default_location_dest_id": cls.stock.id,
            }
        )
        cls.pick_type_reserve_food = cls.env["stock.picking.type"].create(
            {
                "name": "Reserve Food",
                "code": "internal",
                "sequence_code": "RESFOOD",
                "warehouse_id": cls.wh.id,
                "use_create_lots": False,
                "use_existing_lots": True,
                "default_location_src_id": cls.location_stock_reserve_food.id,
                "default_location_dest_id": cls.stock.id,
            }
        )
        cls.pick_type_routing_op = cls.env["stock.picking.type"].create(
            {
                "name": "Dynamic Routing",
                "code": "internal",
                "sequence_code": "WH/HO",
                "warehouse_id": cls.wh.id,
                "use_create_lots": False,
                "use_existing_lots": True,
                "default_location_src_id": cls.location_stock_reserve.id,
                "default_location_dest_id": cls.location_stock_reserve_food.id,
            }
        )
        cls.routing = cls.env["stock.routing"].create(
            {
                "location_id": cls.location_stock_reserve.id,
                "picking_type_id": cls.warehouse.pick_type_id.id,
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "method": "pull",
                            "picking_type_id": cls.pick_type_routing_op.id,
                        },
                    )
                ],
            }
        )
        cls.reserve_route = cls.env["stock.route"].create(
            {
                "name": "Reserve => Stock",
                "rule_ids": [
                    Command.create(
                        {
                            "name": "Reserve => Stock",
                            "action": "pull",
                            "picking_type_id": cls.pick_type_reserve.id,
                            "location_src_id": cls.location_stock_reserve.id,
                            "location_dest_id": cls.stock.id,
                        }
                    )
                ],
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product Food",
                "type": "product",
            }
        )

    @classmethod
    def _create_orderpoint(
        cls, location_dest=None, **kwargs
    ) -> StockLocationOrderpoint:
        location_orderpoint = Form(cls.env["stock.location.orderpoint"])
        location_orderpoint.location_id = location_dest or cls.location_dest
        for field, value in kwargs.items():
            setattr(location_orderpoint, field, value)
        return location_orderpoint.save()

    @classmethod
    def _create_quantity(cls, location, quantity, product=False):
        product = product or cls.product
        cls.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": product.id,
                "quantity": quantity,
                "location_id": location.id,
            }
        )._apply_inventory()
