"""Post-init hook: remove unique constraint on stock.lot for live crop products."""


def post_init_hook(env):
    """Drop the unique constraint on stock.lot(name, product_id, company_id)
    so duplicate live lot names (same YY-WW) are allowed.
    """
    env.cr.execute("""
        ALTER TABLE stock_lot
        DROP CONSTRAINT IF EXISTS stock_lot_name_product_company_uniq;
    """)
