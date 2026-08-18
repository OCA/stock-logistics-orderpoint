# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestSchedulerIntegration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.hub = cls.warehouse.lot_stock_id
        cls.product = cls.env["product.product"].create(
            {"name": "Strength Test Product", "is_storable": True}
        )
        cls.spoke_a = cls.env["stock.location"].create(
            {
                "name": "Spoke A",
                "usage": "internal",
                "location_id": cls.warehouse.view_location_id.id,
            }
        )
        cls.spoke_b = cls.env["stock.location"].create(
            {
                "name": "Spoke B",
                "usage": "internal",
                "location_id": cls.warehouse.view_location_id.id,
            }
        )
        cls.internal_picking_type = cls.env.ref("stock.picking_type_internal")
        cls.route = cls.env["stock.route"].create({"name": "Hub to Spokes"})
        cls._create_rule(cls.route, cls.hub, cls.spoke_a, cls.internal_picking_type)
        cls._create_rule(cls.route, cls.hub, cls.spoke_b, cls.internal_picking_type)
        cls.move_model = cls.env["stock.move"]

    @classmethod
    def _create_rule(cls, route, source, destination, picking_type, **values):
        return cls.env["stock.rule"].create(
            {
                "name": f"{source.name} -> {destination.name}",
                "action": "pull",
                "location_src_id": source.id,
                "location_dest_id": destination.id,
                # Off by default, and then the move goes wherever the picking
                # type points instead of where the rule says.
                "location_dest_from_rule": True,
                "route_id": route.id,
                "picking_type_id": picking_type.id,
                "warehouse_id": cls.warehouse.id,
                **values,
            }
        )

    def _create_orderpoint(self, location, route=None, **values):
        return self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product.id,
                "location_id": location.id,
                "warehouse_id": self.warehouse.id,
                "route_id": (route or self.route).id,
                "product_min_qty": 10,
                "product_max_qty": 15,
                "trigger": "auto",
                **values,
            }
        )

    def _set_strength(self, location, strength):
        return self.env["stock.orderpoint.strength"].create(
            {
                "location_id": location.id,
                "strength": strength,
                "date_start": date(2000, 1, 1),
                "date_stop": date(2100, 1, 1),
            }
        )

    def _set_hub_quantity(self, qty):
        self.env["stock.quant"]._update_available_quantity(self.product, self.hub, qty)

    def _run_scheduler(self):
        self.env["stock.rule"]._run_scheduler_tasks(company_id=self.env.company.id)

    def _moves_for(self, orderpoint):
        return self.move_model.search([("orderpoint_id", "=", orderpoint.id)])

    def _moves_out_of_hub(self, orderpoint):
        return self._moves_for(orderpoint).filtered(
            lambda move: move.location_id == self.hub
        )

    def _assert_move(self, moves, demand, reserved):
        self.assertEqual(sum(moves.mapped("product_uom_qty")), demand)
        self.assertEqual(sum(moves.mapped("quantity")), reserved)

    @contextmanager
    def _floor_on_the_hub(self, floor):
        """Stand in for anything that keeps part of the source out of reach.

        A replenishment reserve, a lot a move may not touch, an owner: this
        module cannot know what, and must not have to.
        """
        move_model = type(self.env["stock.move"])
        original = move_model._update_reserved_quantity

        def capped(move, need, location_id, *args, **kwargs):
            available = move.env["stock.quant"]._get_available_quantity(
                move.product_id, location_id
            )
            need = min(need, max(0.0, available - floor))
            return original(move, need, location_id, *args, **kwargs)

        with patch.object(move_model, "_update_reserved_quantity", capped):
            yield

    def test_contended_run(self):
        """The demand stays whole; only what exists gets shared out."""
        self._set_hub_quantity(6)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=2)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=4)

    def test_a_share_is_whole_units_by_default(self):
        """Two thirds of a robot is no use to the shop that asked for one."""
        self._set_hub_quantity(10)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        # 3.33 and 6.67 before rounding; the unit left over goes to the heavier.
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=3)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=7)

    def test_stock_out_of_reach_is_not_shared_out(self):
        """The split covers what can be had, not what the source says is free.

        Sharing out the whole of free_qty gives each move a share larger than
        it can take, and the part it cannot take goes to whoever reserves next
        -- so the heavier the claim, the later it is served.
        """
        self._set_hub_quantity(16)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        with self._floor_on_the_hub(10):
            self._run_scheduler()
        # 6 within reach, split 1 to 2.
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=2)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=4)

    def test_rechecking_availability_holds_the_total(self):
        """Check Availability on one transfer must not empty another.

        Reshuffling releases what a move holds beyond its share, and that stock
        has to reach the move whose share it now is. If the split was over
        stock that could not be had, it does not: the transfer that was checked
        absorbs it and its competitor is left with nothing.
        """
        self._set_hub_quantity(16)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        strength_b = self._set_strength(self.spoke_b, 2.0)
        with self._floor_on_the_hub(10):
            self._run_scheduler()
            strength_b.strength = 0.5
            self._moves_out_of_hub(orderpoint_a).picking_id.action_assign()
        moves_a = self._moves_for(orderpoint_a)
        moves_b = self._moves_for(orderpoint_b)
        self.assertEqual(
            sum((moves_a | moves_b).mapped("quantity")),
            6,
            "the group gave up stock that reached nobody",
        )
        self._assert_move(moves_a, demand=15, reserved=4)
        self._assert_move(moves_b, demand=15, reserved=2)

    def test_no_contention(self):
        self._set_hub_quantity(40)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=15)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=15)

    def test_no_strength_records_splits_evenly(self):
        """Installing the module is enough to change how stock is shared.

        Every location weighs 1 until someone says otherwise, so contended
        stock is split evenly rather than going to whoever asked first.
        """
        self._set_hub_quantity(10)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=5)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=5)

    def test_restock_tops_up_the_existing_transfers(self):
        """Nothing is reordered once the stock arrives: the demand was there all along.

        The next scheduler pass reassigns the moves it left partially available,
        and with enough to go round the weighting steps aside.
        """
        self._set_hub_quantity(6)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        self.assertEqual(orderpoint_a.qty_to_order_computed, 0)

        self._set_hub_quantity(100)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=15)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=15)

    def test_late_competitor_takes_its_share_back(self):
        """A move confirmed on its own reserves all it can, and must give it back.

        Otherwise the split would only ever come out right on a run that creates
        every competing move at once.
        """
        self._set_hub_quantity(6)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=6)

        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=2)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=4)

    def test_a_picked_move_is_left_alone(self):
        """Whoever already went to fetch the goods keeps them."""
        self._set_hub_quantity(6)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        self._run_scheduler()
        self._moves_for(orderpoint_a).picked = True

        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=6)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=0)

    def test_reservation_snaps_to_the_replenishment_unit(self):
        """Half a pack is no use to whoever has to ship it."""
        pack_of_6 = self.env.ref("uom.product_uom_pack_6")
        self.product.uom_ids += pack_of_6
        self._set_hub_quantity(15)
        orderpoint_a = self._create_orderpoint(
            self.spoke_a, product_max_qty=10, replenishment_uom_id=pack_of_6.id
        )
        orderpoint_b = self._create_orderpoint(
            self.spoke_b, product_max_qty=10, replenishment_uom_id=pack_of_6.id
        )
        self._run_scheduler()
        # 7.5 apiece rounded down to whole packs, and the 3 left over are of no
        # use to either.
        self._assert_move(self._moves_for(orderpoint_a), demand=12, reserved=6)
        self._assert_move(self._moves_for(orderpoint_b), demand=12, reserved=6)

    def test_order_once_takes_what_it_finds(self):
        """A human asking for a quantity is never throttled.

        Nothing competes for the stock at the moment they ask, so the weighting
        has nothing to arbitrate and the transfer reserves everything there is.
        """
        self._set_hub_quantity(6)
        orderpoint_a = self._create_orderpoint(self.spoke_a)
        self._create_orderpoint(self.spoke_b)
        self._set_strength(self.spoke_b, 2.0)
        orderpoint_a.action_replenish()
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=6)

    def test_two_step_resupply_weighs_the_move_out_of_the_hub(self):
        """Resupply between warehouses goes hub -> transit -> spoke.

        The move the orderpoint raises starts at the transit, which holds
        nothing; the one that draws on the contended stock is the move feeding
        it, and the orderpoint follows down the chain to reach it.

        Each spoke needs a transit of its own, or the two moves out of the hub
        differ in nothing at all and Odoo merges them into one before there is
        anything left to arbitrate.
        """
        route = self.env["stock.route"].create({"name": "Hub to Spokes in two steps"})
        for spoke in (self.spoke_a, self.spoke_b):
            transit = self.env["stock.location"].create(
                {"name": f"Transit to {spoke.name}", "usage": "transit"}
            )
            self._create_rule(route, self.hub, transit, self.internal_picking_type)
            self._create_rule(
                route,
                transit,
                spoke,
                self.internal_picking_type,
                procure_method="make_to_order",
            )

        self._set_hub_quantity(6)
        orderpoint_a = self._create_orderpoint(self.spoke_a, route=route)
        orderpoint_b = self._create_orderpoint(self.spoke_b, route=route)
        self._set_strength(self.spoke_b, 2.0)
        self._run_scheduler()
        self._assert_move(self._moves_out_of_hub(orderpoint_a), demand=15, reserved=2)
        self._assert_move(self._moves_out_of_hub(orderpoint_b), demand=15, reserved=4)

    def test_transfers_without_a_reordering_rule_are_left_alone(self):
        """A hand made transfer keeps its stock, and lends none of it out.

        Whether a move takes part is decided by orderpoint_id alone, which core
        only fills in for a rule whose trigger is Auto.
        """
        bench = self.env["stock.location"].create(
            {
                "name": "Bench",
                "usage": "internal",
                "location_id": self.warehouse.view_location_id.id,
            }
        )
        by_hand = self.env["stock.picking"].create(
            {
                "picking_type_id": self.internal_picking_type.id,
                "location_id": self.hub.id,
                "location_dest_id": bench.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 4,
                            "location_id": self.hub.id,
                            "location_dest_id": bench.id,
                        },
                    )
                ],
            }
        )
        self._set_hub_quantity(6)
        by_hand.action_confirm()
        by_hand.action_assign()
        self.assertFalse(by_hand.move_ids.orderpoint_id)
        self._assert_move(by_hand.move_ids, demand=4, reserved=4)

        orderpoint_a = self._create_orderpoint(self.spoke_a)
        orderpoint_b = self._create_orderpoint(self.spoke_b)
        self._run_scheduler()
        # Untouched, and unpicked: only the 2 it left free are shared out.
        self.assertFalse(by_hand.move_ids.picked)
        self._assert_move(by_hand.move_ids, demand=4, reserved=4)
        self._assert_move(self._moves_for(orderpoint_a), demand=15, reserved=1)
        self._assert_move(self._moves_for(orderpoint_b), demand=15, reserved=1)

    def test_a_manual_trigger_rule_is_left_alone(self):
        """Core only stamps orderpoint_id on a move when the trigger is Auto."""
        self._set_hub_quantity(6)
        manual = self._create_orderpoint(self.spoke_a, trigger="manual")
        manual.action_replenish()
        moves = self.move_model.search(
            [
                ("product_id", "=", self.product.id),
                ("location_dest_id", "=", self.spoke_a.id),
            ]
        )
        self.assertFalse(moves.orderpoint_id)
        self.assertFalse(moves._is_strength_arbitrable())

    def test_supplier_sourced_orderpoint_is_left_alone(self):
        """A vendor never runs short, so there is nothing to arbitrate."""
        route = self.env["stock.route"].create({"name": "Buy from vendor"})
        self._create_rule(
            route,
            self.env.ref("stock.stock_location_suppliers"),
            self.spoke_a,
            self.env.ref("stock.picking_type_in"),
        )

        orderpoint = self._create_orderpoint(self.spoke_a, route=route)
        self._run_scheduler()
        self._assert_move(self._moves_for(orderpoint), demand=15, reserved=15)
