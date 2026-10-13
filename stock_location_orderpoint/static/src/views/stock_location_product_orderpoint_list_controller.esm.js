/** @odoo-module */

import {ListController} from "@web/views/list/list_controller";

export class StockLocationProductOrderpointListController extends ListController {
    async onClickReplenish() {
        const resIds = await this.getSelectedResIds();
        const action = await this.model.orm.call(
            this.props.resModel,
            "action_replenish",
            [resIds],
            {
                context: this.props.context,
            }
        );
        if (action) {
            await this.actionService.doAction(action);
        }
        return this.actionService.doAction("stock.action_replenishment", {
            stackPosition: "replaceCurrentAction",
        });
    }
}
