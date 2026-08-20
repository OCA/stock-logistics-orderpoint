# © 2024 Solvos Consultoría Informática (<http://www.solvos.es>)
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

{
    "name": "Stock Orderpoints - Redefined name by product",
    "summary": """
        Makes stock minimum warehouse rule name visible in list view and
        renames them using product code (or name), so identifying
        them when used as origin in e.g. a PO is easier
    """,
    "author": "Solvos, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "depends": ["stock"],
    "data": ["views/stock_warehouse_orderpoint.xml"],
}
