# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from .common import TestLocationOrderpointCommon


class TestLocationOrderpoint(TestLocationOrderpointCommon):
    def test_manual_replenishment_with_purchase(self):
        """
        If a purchase order is confirmed and reception will replenish
        Stock location directly, the virtual available quantity will
        be fullfiled by this incoming quantity. As we don't want to
        take those quantities into account in order to replenish directly,
        we need to exclude some locations from the available quantities (e.g.: Suppliers).
        """
        orderpoint, location_src = self._create_orderpoint_complete(
            "Stock2", trigger="manual"
        )
        orderpoint2, location_src2 = self._create_orderpoint_complete(
            "Stock2.2", trigger="manual"
        )

        orderpoint.stock_excluded_location_domain = [
            ("location_id.usage", "!=", "supplier")
        ]

        self.assertEqual(orderpoint.location_src_id, location_src)
        move = self._create_outgoing_move(12)
        move = self._create_outgoing_move(1)
        self.assertEqual(move.state, "confirmed")

        orderpoints = orderpoint | orderpoint2
        self._run_replenishment(orderpoints)

        replenish_move = self._get_replenishment_move(orderpoints)
        self.assertFalse(replenish_move)

        self._create_quants(self.product, location_src, 12)

        # Create an incoming movement from Suppliers -> Stock without validating it.
        self._create_move(
            "Receipt",
            30.0,
            self.env.ref("stock.stock_location_suppliers"),
            self.location_dest,
        )
        self._run_replenishment(orderpoints)
        replenish_move = self._get_replenishment_move(orderpoints)
        self._assert_replenishment_move(replenish_move, 12, orderpoint)
