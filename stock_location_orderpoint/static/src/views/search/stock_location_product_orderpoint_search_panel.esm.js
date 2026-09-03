/** @odoo-module **/

import {SearchPanel} from "@web/search/search_panel/search_panel";

export class StockLocationProductOrderpointSearchPanel extends SearchPanel {
    setup() {
        super.setup(...arguments);
        this.selectedOrderpoint = false;
    }

    // ---------------------------------------------------------------------
    // Actions / Getters
    // ---------------------------------------------------------------------

    get orderpoints() {
        return this.env.searchModel.getOrderpoints();
    }

    clearOrderpointFilter() {
        this.env.searchModel.resetSelectedOrderpoint();
        this.selectedOrderpoint = null;
    }

    selectOrderpoint(orderpoint_id) {
        this.env.searchModel.setSelectedOrderpoint(orderpoint_id);
        this.selectedOrderpoint = orderpoint_id;
    }

    recomputeProductOrderpoints(orderpoint_id) {
        this.env.searchModel.recomputeProductOrderpoints(orderpoint_id);
    }
}

StockLocationProductOrderpointSearchPanel.template =
    "stock_location_orderpoint.StockLocationProductOrderpointSearchPanel";
