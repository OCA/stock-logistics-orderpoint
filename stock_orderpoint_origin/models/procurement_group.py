# Copyright 2021-2022 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, models


class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    @api.model
    def run(self, procurements, raise_user_error=True):
        # Store the reorder source Procurement Groups
        # To be used for reference and link navigation
        # Also updates the Origin field of the PO
        Forecast = self.env["stock.forecasted_product_product"]
        new_procurements = []
        for procurement in procurements:
            ForecastWH = Forecast
            if warehouse := procurement.values.get("warehouse_id"):
                ForecastWH = Forecast.with_context(warehouse=warehouse.id)
            product = procurement.product_id
            data = ForecastWH._get_report_data(product_ids=product.ids)
            source_docs = set()  # Avoid duplicate sources
            for line in data["lines"]:
                if not line["document_in"] and (doc_out_dict := line["document_out"]):
                    source_doc = self.env[doc_out_dict["_name"]].browse(
                        doc_out_dict["id"]
                    )
                    source_docs.add(source_doc)
            if source_docs:
                # stock.picking object doesn't have field procurement_group_id,
                # so we check if the source document is a picking to use the
                # correct field (group_id)
                source_groups = [
                    x.procurement_group_id if x._name != "stock.picking" else x.group_id
                    for x in source_docs
                ]
                source_groups = self.env["procurement.group"].browse(
                    proc.id for proc in source_groups if proc
                )
                source_names = ", ".join([x.name for x in source_docs])
                new_origin = self.env._(
                    "%(source_names)s (from %(procurement_origin)s)",
                    source_names=source_names,
                    procurement_origin=procurement.origin,
                )
                new_procurement = procurement._replace(origin=new_origin)
                new_procurement.values["source_group_ids"] = source_groups
                new_procurements.append(new_procurement)
            else:
                new_procurements.append(procurement)
        return super().run(new_procurements, raise_user_error=raise_user_error)
