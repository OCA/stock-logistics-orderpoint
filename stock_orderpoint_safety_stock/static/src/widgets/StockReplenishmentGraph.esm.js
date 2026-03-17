/*
    Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
    License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
*/

import {ReplenishmentGraphWidget} from "@stock/widgets/json_widget";
import {cookie} from "@web/core/browser/cookie";
import {getColor} from "@web/core/colors/colors";
import {patch} from "@web/core/utils/patch";

patch(ReplenishmentGraphWidget.prototype, {
    get safetyStockMethod() {
        return this.jsonValue.safety_stock_method ?? "manual";
    },
    get standardDeviation() {
        return this.jsonValue.std_dev;
    },
    get safetyStock() {
        return this.jsonValue.safety_stock;
    },
    getScatterGraphConfig() {
        const config = super.getScatterGraphConfig();
        const safetyStockLineColor = getColor(1, cookie.get("color_scheme"), "sm");
        // Add the safety stock line to the graph
        config.data.datasets.push({
            type: "line",
            data: this.jsonValue.safety_stock_line_vals,
            fill: false,
            pointStyle: false,
            borderColor: safetyStockLineColor,
            borderDash: [6, 6],
        });
        // Show the safety stock tick label
        const originalBeforeTickToLabelConversion =
            config.options.scales.y.beforeTickToLabelConversion;
        const originalTicksCallback = config.options.scales.y.ticks.callback;
        config.options.scales.y.beforeTickToLabelConversion = (data) => {
            originalBeforeTickToLabelConversion(data);
            data.ticks.push({value: this.safetyStock});
        };
        config.options.scales.y.ticks.callback = (tick) =>
            tick === this.safetyStock ? this.safetyStock : originalTicksCallback(tick);
        // Adjust the y-axis to show the safety stock line
        config.options.scales.y.suggestedMin = Math.min(
            config.options.scales.y.suggestedMin,
            this.safetyStock * 0.975
        );
        return config;
    },
});
