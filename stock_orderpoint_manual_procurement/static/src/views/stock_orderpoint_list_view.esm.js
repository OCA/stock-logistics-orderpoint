import {StockOrderpointListController} from "@stock/views/stock_orderpoint_list_controller";
import {patch} from "@web/core/utils/patch";

patch(StockOrderpointListController.prototype, {
    async onClickManualOrder() {
        const selectedIds = await this.getSelectedResIds();
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "make.procurement.orderpoint",
            views: [[false, "form"]],
            target: "new",
            context: {
                active_model: "stock.warehouse.orderpoint",
                active_ids: selectedIds,
            },
        });
    },
});
