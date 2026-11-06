import sqlite3

db_path = "/home/ubuntu/FTMO_Stellar_Lite/trading_ny_open.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. Asegurar columnas en trades y account_state
for col in (
    "ALTER TABLE trades ADD COLUMN gross_pnl REAL DEFAULT 0.0",
    "ALTER TABLE trades ADD COLUMN commission REAL DEFAULT 0.0",
    "ALTER TABLE trades ADD COLUMN spread_cost REAL DEFAULT 0.0",
    "ALTER TABLE trades ADD COLUMN is_break_even INTEGER DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN mt5_ticket INTEGER DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN mt5_deal_ticket INTEGER DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN swap REAL DEFAULT 0.0",
    "ALTER TABLE trades ADD COLUMN magic INTEGER DEFAULT 0",
    "ALTER TABLE account_state ADD COLUMN drawdown_type TEXT DEFAULT 'STATIC'",
    "ALTER TABLE account_state ADD COLUMN high_water_mark REAL DEFAULT 0.0",
    "ALTER TABLE account_state ADD COLUMN trailing_max_loss_floor REAL DEFAULT 0.0",
    "ALTER TABLE account_state ADD COLUMN consistency_rule_pct REAL DEFAULT 0.0",
):
    try:
        cur.execute(col)
    except Exception:
        pass

# 2. Aislar US500 fantasma
cur.execute("UPDATE trades SET status = 'GHOST_EXCLUDED', notes = notes || ' | EXCLUIDO_POR_NO_EXISTIR_EN_MT5' WHERE symbol LIKE '%500%' OR symbol LIKE '%ES%'")

# 3. Corregir deals de hoy al centavo exacto de MT5
cur.execute("UPDATE trades SET exit_price = 4084.06, pnl = -40.86, gross_pnl = -40.73, swap = -0.13, mt5_ticket = 11258345490, mt5_deal_ticket = 11021606449 WHERE symbol LIKE '%GC%' OR symbol LIKE '%XAU%'")
cur.execute("UPDATE trades SET exit_price = 1.12233, pnl = -51.84, gross_pnl = -51.84, swap = 0.0, mt5_ticket = 11259592948, mt5_deal_ticket = 11013706928 WHERE symbol LIKE '%EUR%'")
cur.execute("UPDATE trades SET exit_price = 157.336, pnl = 102.18, gross_pnl = 102.28, swap = -0.10, mt5_ticket = 11261186089, mt5_deal_ticket = 11021603343 WHERE symbol LIKE '%JPY%'")

# 4. Actualizar account_state a $10,109.74 exacto
cur.execute("UPDATE account_state SET balance = 10109.74, equity = 10109.74, high_water_mark = 10109.74 WHERE id = 1")
conn.commit()

cur.execute("SELECT balance, equity, high_water_mark FROM account_state WHERE id = 1")
print("VPS Database Reconciled Successfully:", cur.fetchone())
conn.close()
