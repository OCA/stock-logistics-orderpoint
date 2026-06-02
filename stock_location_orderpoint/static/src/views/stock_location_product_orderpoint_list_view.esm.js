/** @odoo-module */

import {listView} from "@web/views/list/list_view";
import {registry} from "@web/core/registry";
import {StockLocationProductOrderpointListController as Controller} from "./stock_location_product_orderpoint_list_controller.esm";
import {StockLocationProductOrderpointSearchModel} from "./search/stock_location_product_orderpoint_search_model.esm";
import {StockLocationProductOrderpointSearchPanel} from "./search/stock_location_product_orderpoint_search_panel.esm";

export const StockLocationProductOrderpointListView = {
    ...listView,
    Controller,
    buttonTemplate: "stock_location_orderpoint.StockLocationProductOrderpoint.Buttons",
    SearchModel: StockLocationProductOrderpointSearchModel,
    SearchPanel: StockLocationProductOrderpointSearchPanel,
};

registry
    .category("views")
    .add(
        "stock_location_product_orderpoint_list",
        StockLocationProductOrderpointListView
    );
