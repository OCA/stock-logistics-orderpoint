# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math
from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass

from odoo import fields, models

ARBITRABLE_STATES = ("confirmed", "waiting", "partially_available", "assigned")
EPSILON = 1e-6


@dataclass(frozen=True)
class Claim:
    """One move's claim on the stock its group is competing for."""

    id: Hashable
    requested: float
    weight: float
    increment: float


def allocate(claims: list[Claim], available: float) -> dict[Hashable, float]:
    """Share `available` between the claims, in proportion to their weight.

    Nobody gets more than they requested; what a satisfied claim leaves behind
    is shared out again among the rest. Weights must be positive, which the
    strength record's own constraint guarantees.
    """
    shares = _split_by_weight(claims, available)
    return _round_to_increments(claims, shares, available)


def _split_by_weight(claims: list[Claim], available: float) -> dict[Hashable, float]:
    """Divide by weight, then divide again whatever the satisfied left behind."""
    allocated = {claim.id: 0.0 for claim in claims}
    unsatisfied = {claim.id: claim for claim in claims}
    remaining = available

    while unsatisfied and remaining > EPSILON:
        total_weight = sum(claim.weight for claim in unsatisfied.values())
        satisfied_ids = []
        for claim in unsatisfied.values():
            share = remaining * claim.weight / total_weight
            still_wanted = claim.requested - allocated[claim.id]
            if share >= still_wanted - EPSILON:
                allocated[claim.id] += still_wanted
                remaining -= still_wanted
                satisfied_ids.append(claim.id)

        if satisfied_ids:
            for claim_id in satisfied_ids:
                del unsatisfied[claim_id]
            continue

        for claim in unsatisfied.values():
            allocated[claim.id] += remaining * claim.weight / total_weight
        break

    return allocated


def _round_to_increments(
    claims: list[Claim],
    shares: dict[Hashable, float],
    available: float,
) -> dict[Hashable, float]:
    """Cut each share back to whole units, then hand the offcuts to the heaviest."""
    allocated = {}
    leftover = available
    for claim in claims:
        if claim.increment > EPSILON:
            units = math.floor(shares[claim.id] / claim.increment + EPSILON)
            allocated[claim.id] = units * claim.increment
        else:
            allocated[claim.id] = shares[claim.id]
        leftover -= allocated[claim.id]

    while True:
        eligible = [
            claim
            for claim in claims
            if claim.increment > EPSILON
            and leftover >= claim.increment - EPSILON
            and allocated[claim.id] + claim.increment <= claim.requested + EPSILON
        ]
        if not eligible:
            break
        best = max(eligible, key=lambda claim: claim.weight)
        allocated[best.id] += best.increment
        leftover -= best.increment

    return allocated


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self, force_qty=False):
        """Share contended stock by strength instead of first come first served.

        Reservation is where the weighting belongs, not demand: every move keeps
        asking for the quantity the reordering rule dictated, and only the part
        that physically exists is split between them.

        Contended stock is reserved twice. The first pass lets the competing
        moves take everything they can, which is the only reliable measure of
        how much there is to share; the second hands back whatever that left in
        the wrong hands. A group the first pass served in full never reaches
        the second, which is how a run with enough to go round costs no more
        than it did.

        Whether a group is short is decided the same way, on what it managed to
        take. Asking the source how much is free would answer for stock the
        moves cannot have, and a group told it has plenty is a group nobody
        arbitrates at all.

        force_qty is left alone, since its callers already know the exact
        quantity they want reserved.
        """
        groups = {} if force_qty else self._get_strength_arbitration_groups()
        if not groups:
            return super()._action_assign(force_qty=force_qty)
        moves = self.browse().union(*groups.values()) | self
        result = super(StockMove, moves)._action_assign()
        caps = moves._get_strength_reservation_caps(groups)
        if not caps:
            return result
        moves._release_over_strength_cap(caps)
        return super(
            StockMove,
            # A tuple of pairs, so that the context stays hashable.
            moves.with_context(strength_reservation_caps=tuple(caps.items())),
        )._action_assign()

    def _update_reserved_quantity(
        self,
        need,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=True,
    ):
        """The one funnel every make to stock reservation passes through."""
        remaining = self._get_strength_remaining_cap()
        if remaining is not None:
            need = min(need, remaining)
            if need <= EPSILON:
                return 0
        return super()._update_reserved_quantity(
            need,
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
        )

    def _get_strength_reservation_caps(self, groups):
        """How much of the contended stock each competing move may reserve.

        The pool is what the group holds once each of them has taken all it
        could, never what the source says is free. Not every free unit can
        really be had -- a lot this move may not touch, a floor another module
        keeps out of reach of replenishment -- and a share that cannot be taken
        does not stay unclaimed: it falls to whoever reserves next, which is
        the arrival order this module exists to replace.

        Keyed by move id, and empty when the first pass already served
        everyone.
        """
        strength_model = self.env["stock.orderpoint.strength"]
        run_date = fields.Date.context_today(self)
        caps = {}
        for group in groups.values():
            available = sum(move._get_strength_reserved_quantity() for move in group)
            claims = [
                Claim(
                    id=move.id,
                    requested=move.product_qty,
                    weight=strength_model._get_effective_strength(
                        move.orderpoint_id.location_id,
                        run_date,
                        move.orderpoint_id.lead_days,
                    ),
                    increment=move.orderpoint_id._get_strength_rounding_increment(),
                )
                for move in group
            ]
            if sum(claim.requested for claim in claims) <= available + EPSILON:
                continue
            caps.update(allocate(claims, available))
        return caps

    def _get_strength_arbitration_groups(self):
        """The competing moves, grouped by the stock they draw on.

        The competitors are searched rather than read off self, because whoever
        asked for the reservation -- a picking's Check Availability button, say
        -- rarely holds the whole group in hand.
        """
        keys = {
            (move.location_id, move.product_id)
            for move in self
            if move._is_strength_arbitrable()
        }
        if not keys:
            return {}
        competing = self.search(
            [
                ("location_id", "in", [location.id for location, _p in keys]),
                ("product_id", "in", [product.id for _l, product in keys]),
                ("state", "in", ARBITRABLE_STATES),
                ("orderpoint_id", "!=", False),
            ]
        )
        groups = defaultdict(lambda: self.browse())
        for move in competing:
            key = (move.location_id, move.product_id)
            if key in keys and move._is_strength_arbitrable():
                groups[key] |= move
        return groups

    def _is_strength_arbitrable(self):
        """Whether this move's claim on its source stock may be rearranged.

        Only automatic replenishment takes part. A delivery to a customer, a
        move a user already picked, and a move whose goods are chained in from
        somewhere else all have a claim this module has no business touching.
        """
        self.ensure_one()
        return bool(
            self.orderpoint_id
            and not self.picked
            and not self.move_orig_ids
            and self.state in ARBITRABLE_STATES
            and self.location_id.usage == "internal"
            and not self._should_bypass_reservation()
        )

    def _release_over_strength_cap(self, caps):
        """Hand back whatever a move holds beyond its share.

        Without this the split would only ever come out right on the run that
        creates every competing move at once: a move confirmed on its own takes
        all it can, and the ones that follow find nothing left to reserve.
        """
        over = self.browse()
        for move in self:
            cap = caps.get(move.id)
            if cap is None:
                continue
            if move._get_strength_reserved_quantity() > cap + EPSILON:
                over |= move
        over._do_unreserve()

    def _get_strength_reserved_quantity(self):
        """What the move holds today, in the unit the allocation works in."""
        self.ensure_one()
        return self.product_uom._compute_quantity(self.quantity, self.product_id.uom_id)

    def _get_strength_remaining_cap(self):
        """What is left of this move's share, or None when it has no cap."""
        self.ensure_one()
        caps = dict(self.env.context.get("strength_reservation_caps") or ())
        if self.id not in caps:
            return None
        return max(caps[self.id] - self._get_strength_reserved_quantity(), 0.0)
