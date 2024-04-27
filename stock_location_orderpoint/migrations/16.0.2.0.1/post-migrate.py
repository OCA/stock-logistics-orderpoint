# Copyright 2024 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(env, version):
    env.cr.execute(
        "UPDATE stock_location_orderpoint "
        "set consuming_move_check_waiting = true "
        "where replenish_method = 'fill_up'"
    )
