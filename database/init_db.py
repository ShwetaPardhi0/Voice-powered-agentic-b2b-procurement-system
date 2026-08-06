"""
Database Initialization Script
Runs schema.sql to create the 11-table structure, then seeds
products, warehouses, inventory, suppliers, and supplier_products
with sample B2B data.
"""

import os
import sys
import json

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(override=True)

from database.connection import get_db_connection


def init_db():
    print("Connecting to PostgreSQL to execute schema.sql...")
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
    except Exception as e:
        print(f"CRITICAL: Cannot connect to database: {e}")
        print("Verify PostgreSQL is running and .env is correct.")
        sys.exit(1)

    # 1. Execute DDL from schema.sql
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        print(f"Error: schema.sql not found at {schema_path}")
        sys.exit(1)

    with open(schema_path, "r") as f:
        schema_sql = f.read()
    cursor.execute(schema_sql)
    print("[OK] Schema loaded (11 tables created)")

    # 2. Seed Products
    products = [
        ("SCR-M8-001", "Steel Screws M8", "Premium strength steel screws, M8 size, corrosion-resistant", "pieces"),
        ("SCR-M6-001", "Steel Screws M6", "Standard steel screws, M6 size, indoor use", "pieces"),
        ("PLT-A36-6", "Steel Plate A36 6mm", "A36 carbon steel plate, 4x8 ft, 6mm thickness", "sheets"),
        ("PLT-A36-10", "Steel Plate A36 10mm", "A36 carbon steel plate, 4x8 ft, 10mm thickness", "sheets"),
        ("ALU-ING-01", "Aluminum Ingot 99.7%", "High-purity aluminum ingot, 99.7% rating", "kg"),
        ("WLD-E6013", "Welding Electrode E6013", "AWS A5.1 welding electrode, 3.15mm", "kg"),
    ]
    for sku, name, desc, unit in products:
        cursor.execute(
            "INSERT INTO products (sku, name, description, unit) VALUES (%s, %s, %s, %s)",
            (sku, name, desc, unit),
        )
    print(f"[OK] Seeded {len(products)} products")

    # 3. Seed Warehouses
    warehouses = [
        ("WH-MUM", "Mumbai Warehouse", "Bhiwandi, Maharashtra"),
        ("WH-DEL", "Delhi Warehouse", "Manesar, Haryana"),
        ("WH-CHE", "Chennai Warehouse", "Sriperumbudur, Tamil Nadu"),
    ]
    for wid, name, loc in warehouses:
        cursor.execute(
            "INSERT INTO warehouses (id, name, location) VALUES (%s, %s, %s)",
            (wid, name, loc),
        )
    print(f"[OK] Seeded {len(warehouses)} warehouses")

    # 4. Seed Inventory
    inventory_rows = [
        ("SCR-M8-001", "WH-MUM", 15000, 5000),
        ("SCR-M8-001", "WH-DEL", 8000, 3000),
        ("SCR-M6-001", "WH-MUM", 20000, 5000),
        ("PLT-A36-6", "WH-MUM", 120, 50),
        ("PLT-A36-6", "WH-DEL", 45, 20),
        ("PLT-A36-10", "WH-MUM", 80, 30),
        ("ALU-ING-01", "WH-CHE", 500, 200),
        ("WLD-E6013", "WH-MUM", 300, 100),
    ]
    for sku, wid, stock, reorder in inventory_rows:
        cursor.execute(
            "INSERT INTO inventory (sku, warehouse_id, stock_level, reorder_threshold) VALUES (%s, %s, %s, %s)",
            (sku, wid, stock, reorder),
        )
    print(f"[OK] Seeded {len(inventory_rows)} inventory records")

    # 5. Seed Suppliers
    suppliers = [
        ("mehta_traders", "Mehta Traders Pvt. Ltd.", "Fasteners & Steel"),
        ("steel_dynamics", "Steel Dynamics India", "Steel Plates & Structural"),
        ("global_alloys", "Global Alloys Corp.", "Non-Ferrous Metals"),
        ("hardware_hub", "Hardware Hub Distributors", "General Hardware"),
    ]
    for sid, name, cat in suppliers:
        cursor.execute(
            "INSERT INTO suppliers (id, name, category) VALUES (%s, %s, %s)",
            (sid, name, cat),
        )
    print(f"[OK] Seeded {len(suppliers)} suppliers")

    # 6. Seed Supplier Products
    supplier_products = [
        ("mehta_traders", "SCR-M8-001", 4.50, 5),
        ("mehta_traders", "SCR-M6-001", 3.80, 5),
        ("mehta_traders", "PLT-A36-6", 8200.00, 7),
        ("steel_dynamics", "PLT-A36-6", 7900.00, 7),
        ("steel_dynamics", "PLT-A36-10", 11500.00, 7),
        ("global_alloys", "ALU-ING-01", 240.00, 5),
        ("hardware_hub", "SCR-M8-001", 5.00, 3),
        ("hardware_hub", "PLT-A36-6", 8500.00, 3),
        ("hardware_hub", "WLD-E6013", 185.00, 2),
    ]
    for sid, sku, price, lead_days in supplier_products:
        cursor.execute(
            "INSERT INTO supplier_products (supplier_id, sku, price, lead_time_days) VALUES (%s, %s, %s, %s)",
            (sid, sku, price, lead_days),
        )
    print(f"[OK] Seeded {len(supplier_products)} supplier-product links")

    cursor.close()
    conn.close()
    print("\n[OK] Database initialization complete.")


if __name__ == "__main__":
    init_db()
