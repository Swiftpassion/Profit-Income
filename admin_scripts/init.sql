-- Create product_costs table
CREATE TABLE IF NOT EXISTS product_costs (
    id SERIAL PRIMARY KEY,
    sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    unit_cost NUMERIC DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sku, platform)
);

CREATE INDEX IF NOT EXISTS idx_product_costs_sku ON product_costs(sku);

-- Create daily_ads_metrics table
CREATE TABLE IF NOT EXISTS daily_ads_metrics (
    date DATE NOT NULL,
    shop_name TEXT NOT NULL,
    ads_amount NUMERIC DEFAULT 0,
    roas_ads NUMERIC DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, shop_name)
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_id TEXT NOT NULL,
    tracking_id TEXT,
    sku TEXT,
    product_name TEXT,
    platform TEXT,
    shop_name TEXT,
    status TEXT,
    quantity INTEGER DEFAULT 0,
    sales_amount NUMERIC DEFAULT 0,
    settlement_amount NUMERIC DEFAULT 0,
    fees NUMERIC DEFAULT 0,
    affiliate NUMERIC DEFAULT 0,
    unit_cost NUMERIC DEFAULT 0,
    total_cost NUMERIC DEFAULT 0,
    net_profit NUMERIC DEFAULT 0,
    created_date TIMESTAMP,
    shipped_date TIMESTAMP,
    settlement_date TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_shop_platform ON orders(shop_name, platform);
CREATE INDEX IF NOT EXISTS idx_orders_created_date ON orders(created_date);
