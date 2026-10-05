# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint XYZ Frequency",
    "summary": """
        Space out the procurement scheduler runs by XYZ classification""",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "author": "Ariel Barreiros, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "category": "Warehouse Management",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/xyz_classification_level.xml",
        "views/xyz_classification_product_level.xml",
        "views/product_template.xml",
        "views/product_product.xml",
    ],
}
