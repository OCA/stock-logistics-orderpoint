/** @odoo-module **/

import {Domain} from "@web/core/domain";
import {SearchModel} from "@web/search/search_model";
import {useService} from "@web/core/utils/hooks";

const {useState} = owl;

export class StockLocationProductOrderpointSearchModel extends SearchModel {
    /**
     * @override
     */
    setup() {
        this.notificationService = useService("notification");
        this.productOrderpointState = useState({
            selectedOrderpoint: null,
            orderpoints: [],
        });
        this._lastOrderpointDomain = null;
        super.setup(...arguments);
    }

    exportState() {
        const state = super.exportState();
        state.selectedOrderpoint = this.productOrderpointState.selectedOrderpoint;
        return state;
    }

    _importState(state) {
        super._importState(...arguments);
        if (state.selectedOrderpoint) {
            this.productOrderpointState.selectedOrderpoint = state.selectedOrderpoint;
        }
    }

    /**
     * @override
     */
    async load() {
        await super.load(...arguments);
        // Store date and stage_id searchItemId in the SearchModel for reuse in other functions.
        for (const searchItem of Object.values(this.searchItems)) {
            if (["dateGroupBy", "groupBy"].includes(searchItem.type)) {
                if (this.stageIdSearchItemId && this.dateSearchItemId) {
                    return;
                }
                switch (searchItem.fieldName) {
                    case "date":
                        this.dateSearchItemId = searchItem.id;
                        break;
                    case "stage_id":
                        this.stageIdSearchItemId = searchItem.id;
                        break;
                }
            }
        }
        await this._loadOrderpoints();
        this._lastOrderpointDomain = JSON.stringify(this._extractOrderpointDomain());
    }

    async _notify() {
        // Guard we are into the inital loading of the view
        if (!this.display) {
            return super._notify();
        }

        const newDomain = JSON.stringify(this._extractOrderpointDomain());

        if (newDomain !== this._lastOrderpointDomain) {
            this._lastOrderpointDomain = newDomain;
            await this._loadOrderpoints();
        }

        super._notify();
    }

    // ---------------------------------------------------------------------
    // Actions / Getters
    // ---------------------------------------------------------------------

    getOrderpoints() {
        return this.productOrderpointState.orderpoints;
    }

    get orderpointFieldsDomain() {
        return ["trigger", "replenish_method"];
    }

    _extractOrderpointDomain() {
        const orderpointDomain = [];
        const domain = this._getDomain();
        for (const domainPart of domain) {
            if (this.orderpointFieldsDomain.includes(domainPart[0])) {
                orderpointDomain.push(domainPart);
            }
        }
        return orderpointDomain;
    }

    async _loadOrderpoints() {
        this.productOrderpointState.orderpoints = await this.orm.call(
            "stock.location.orderpoint",
            "search_read",
            [],
            {
                context: this.context,
                fields: ["name", "id"],
                domain: this._extractOrderpointDomain(),
            }
        );

        // If the currently selected orderpoint is not in the loaded orderpoints,
        // reset the selected orderpoint.
        const ids = this.productOrderpointState.orderpoints.map((o) => o.id);
        if (
            this.productOrderpointState.selectedOrderpoint &&
            !ids.includes(this.productOrderpointState.selectedOrderpoint)
        ) {
            this.productOrderpointState.selectedOrderpoint = null;
        }
    }

    setSelectedOrderpoint(orderpointId) {
        this.productOrderpointState.selectedOrderpoint = orderpointId;
        this._notify();
    }

    resetSelectedOrderpoint() {
        this.productOrderpointState.selectedOrderpoint = null;
        this._notify();
    }

    _getDomain(params = {}) {
        const domain = super._getDomain(params);

        if (!this.productOrderpointState.selectedOrderpoint) {
            return domain;
        }
        const result = Domain.and([
            domain,
            [
                [
                    "stock_location_orderpoint_id",
                    "=",
                    this.productOrderpointState.selectedOrderpoint,
                ],
            ],
        ]);
        return params.raw ? result : result.toList();
    }

    async recomputeProductOrderpoints(orderpointId) {
        await this.orm.call(
            "stock.location.product.orderpoint",
            "action_recompute_demand",
            ["", orderpointId]
        );
        this.notificationService.add(this.env._t("Orderpoint recomputation done"), {
            type: "success",
        });
        this._notify();
    }
}
