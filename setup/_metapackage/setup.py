import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-stock-logistics-orderpoint",
    description="Meta package for oca-stock-logistics-orderpoint Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-stock_location_orderpoint>=16.0dev,<16.1dev',
        'odoo-addon-stock_orderpoint_move_link>=16.0dev,<16.1dev',
        'odoo-addon-stock_orderpoint_purchase_link>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
