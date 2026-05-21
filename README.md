# Unicenta POS → ERPNext Integration

Sync your **Unicenta POS** data to **ERPNext** — products, customers, and sales invoices — via a Python CLI tool that reads directly from Unicenta's MariaDB/MySQL database and pushes to the ERPNext REST API.

---

## Features

- **Product Sync** — Push Unicenta products (name, price, category) to ERPNext Items
- **Sales Sync** — Push completed POS tickets to ERPNext Sales Invoices with line items and payment entries
- **Customer Sync** — Auto-create ERPNext customers from Unicenta customer records
- **Idempotent** — Safe to run repeatedly; already-synced records are skipped
- **Dry-Run Mode** — Preview what would be synced without making changes

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Unicenta POS   │────▶│  Integration     │────▶│  ERPNext       │
│  (MariaDB/MySQL)│     │  Tool (Python)   │     │  (REST API)    │
└─────────────────┘     └──────────────────┘     └────────────────┘
                              │
                         Reads directly       Pushes via
                         from MySQL DB        /api/resource/
```

The tool connects directly to Unicenta's MySQL/MariaDB database and maps tables to ERPNext doctypes:

| Unicenta Table | ERPNext DocType |
|----------------|-----------------|
| `PRODUCTS` + `CATEGORIES` | `Item` |
| `CUSTOMERS` | `Customer` |
| `RECEIPTS` + `TICKETS` + `TICKETLINES` | `Sales Invoice` |
| `PAYMENTS` | Payment entries within invoice |
| `TAXES` | Item tax lookups |

---

## Requirements

- Python 3.10+
- MariaDB 10.6+ or MySQL 8.0+ (for Unicenta)
- ERPNext instance v14+ with API access enabled

## Installation

```bash
# Clone the repo
git clone https://github.com/BaderSpace/ERPnext_Unicenta-POS.git
cd ERPnext_Unicenta-POS

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp .env.example .env
```

## Configuration

Edit `.env` with your database and ERPNext credentials:

```ini
# Unicenta POS Database
UNICENTA_DB_HOST=localhost
UNICENTA_DB_PORT=3306
UNICENTA_DB_USER=unicentaopos
UNICENTA_DB_PASSWORD=your_db_password
UNICENTA_DB_NAME=unicentaopos

# ERPNext Instance
ERPNEXT_URL=https://your-erpnext.frappe.cloud
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# Sync Options
SYNC_PRODUCTS=true
SYNC_SALES=true
SALES_SYNC_SINCE_DAYS=7
```

### Getting ERPNext API Credentials

1. In ERPNext, go to **Settings → Users → Open User**
2. Under **API Access**, generate an **API Key** and **API Secret**
3. The user must have the appropriate roles (e.g., `System Manager`, `Sales Manager`, `Item Manager`)

---

## Usage

### Preview Changes (Dry Run)

```bash
python main.py --dry-run
```

Example output:
```
=== DRY RUN MODE ===
Would sync 142 products across 8 categories
Would sync 37 tickets (184 lines, 37 payments)
```

### Sync Everything

```bash
python main.py --sync all
```

### Sync Only Products

```bash
python main.py --sync products
```

### Sync Only Sales (Last 7 Days)

```bash
python main.py --sync sales
```

### Sync Sales from a Custom Window

```bash
python main.py --sync sales --sales-since 1
python main.py --sync sales --sales-since 30
```

---

## Database Setup

If you're setting up Unicenta from scratch, create the database and use the bundled schema:

```sql
CREATE DATABASE unicentaopos CHARACTER SET utf8 COLLATE utf8_general_ci;
CREATE USER 'unicentaopos'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON unicentaopos.* TO 'unicentaopos'@'localhost';
FLUSH PRIVILEGES;
```

Then run the integration tool — it expects the standard Unicenta schema with these tables:
- `PRODUCTS`, `CATEGORIES`, `TAXES`, `TAXCATEGORIES`
- `CUSTOMERS`
- `RECEIPTS`, `TICKETS`, `TICKETLINES`, `PAYMENTS`, `TAXLINES`

---

## ERPNext Setup

Before syncing, ensure the following exist in your ERPNext instance:

1. **Item Tax Templates** — Create templates matching your tax rates (e.g., "GST 18%", "VAT 10%")
2. **POS Customer** — Create a default customer named `POS Customer` for walk-in sales
3. **Mode of Payment** — Ensure these modes exist: `Cash`, `Bank`, `Credit` (used for payment mapping)
4. **Item Group** — Match categories or create a `Products` group

### Payment Method Mapping

| Unicenta Payment | ERPNext Mode of Payment |
|-----------------|------------------------|
| Cash | Cash |
| Card / Credit Card / Debit Card | Bank |
| Cheque / Check | Bank |
| Mobile | Bank |
| Credit | Credit |
| Other | Cash |

---

## Project Structure

```
Unicenta_ERPnext/
├── .env                    # Credentials (gitignored)
├── .env.example            # Configuration template
├── requirements.txt
├── main.py                 # CLI entry point
└── src/
    ├── config.py           # Environment-based config
    ├── unicenta/
    │   ├── models.py       # Unicenta data models
    │   └── db.py           # MySQL/MariaDB reader
    ├── erpnext/
    │   └── client.py       # ERPNext REST API client
    └── sync/
        ├── products.py     # Product sync logic
        └── sales.py        # Sales invoice sync logic
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Can't connect to MySQL server` | Check `UNICENTA_DB_HOST`/`PORT`, ensure MariaDB is running |
| `ERPNext 403 Forbidden` | Verify API credentials, ensure user has correct roles |
| `Item not found during sales sync` | Run product sync first, or ensure REFERENCE codes exist in ERPNext |
| `Tax not calculated` | Pass `item_tax_template` in the item or configure taxes in ERPNext item defaults |
| `Duplicate invoice errors` | The tool uses idempotency keys — already-synced invoices are skipped |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

Distributed under the GNU General Public License v3.0. See `LICENSE` for more information.
