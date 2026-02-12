# Pombot Handler - Store Management Bot

<br>

<div align="center">
  <img src="https://img.shields.io/badge/Pombot-Handler-2c3e50?style=for-the-badge&logo=telegram&logoColor=white" alt="Pombot Logo"/>
  <br>
  <br>
  <h2>Automated Sales, Expenses & Inventory Management System for <a href="https://pombero.com.ar/">Pombero</a>.</h2>
</div>


<div align="center">
  <a href="#">
    <img src="https://img.shields.io/badge/Client-Pombero-000?style=for-the-badge&logo=shopify&logoColor=white" alt="Client"/>
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/Platform-Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram"/>
  </a>
</div>

---

<div align="center">
  <img src="https://img.shields.io/badge/Status-Production-success" alt="Status"/>
  <img src="https://img.shields.io/badge/Coverage->75%25-green" alt="Coverage"/>
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/Cloud-AWS%20Lambda-orange" alt="Cloud"/>
</div>


## Architecture & Design Principles

### 🧩 Key Patterns Implemented
*   **Layered Architecture**: Strict separation of concerns:
    *   **Handlers (`handlers/`)**: Telegram interaction & state management (Controller).
    *   **Services (`services/`)**: Business logic & data integration (Model).
    *   **Lambdas (`lambdas/`)**: Background tasks & webhooks (Async Workers).
*   **Dependency Injection**: Service dependencies are injected or factored out to allow easy mocking during tests.
*   **Factory Pattern**: Centralized creation of complex test objects (`tests/helpers/telegram_factories.py`) ensuring consistent test data.
*   **Async/Await**: Fully asynchronous core to handle high-concurrency Telegram updates efficiently.


## Features & Capabilities


### 1. 📊 Comprehensive Management
- **Sales & Wholesale**: Record transactions, manage payments (partial/full), and track inventory.
- **Expenses**: Categorized expense tracking (Suppliers, Services, Personal) with sub-category logic.
- **Debts**: Track and update outstanding debts with modification flows.

### 2. 🔄 Background Synchronization (`Lambda`)
- **TiendaNube Sync**: Automatically syncs product stock and prices from TiendaNube to Google Sheets.
- **Webhooks**: Real-time order processing (Order Paid -> Record Sale).
- **Scheduler**: Daily expiration checks for Checks and Future Payments, sending Telegram alerts.

### 3. 🛡️ Robust Testing Suite
- **Unit Tests**: >75% coverage across all modules.
- **Mocking**: Extensive use of `unittest.mock` to isolate business logic from external APIs (Telegram, Google Sheets).
- **Regression**: Dedicated suite to prevent re-occurrence of critical bugs.


## Project Structure

```bash
├── handlers/               # 📍 Telegram Handlers (Controllers)
│   ├── sales.py            #    - Sales Flow
│   ├── expenses.py         #    - Expense Tracking
│   ├── wholesale.py        #    - Wholesale & Payments
│   └── ...
├── services/               # 🧠 Business Logic
│   ├── products_service.py #    - Inventory & Options
│   ├── sheets_connection.py#    - Database (Google Sheets)
│   └── ...
├── lambdas/                # ⚡ AWS Lambda Functions
│   ├── lambda_sync.py      #    - Config & Sync Logic
│   └── webhook_handler.py  #    - Event Processing
├── config/                 # ⚙️ Configuration
│   ├── settings.py         #    - Env Vars & Secrets
│   └── definitions.py      #    - Business Constants
├── common/                 # 🔧 Shared Utilities
│   └── utils.py            #    - Parsing & Formatting
├── tests/                  # 🧪 Test Suite
│   ├── unit/               #    - Unit Tests
│   ├── integration/        #    - Flow Tests
│   └── helpers/            #    - Test Factories
└── requirements.txt        # 📦 Dependencies
```

## Setup & Execution

### Prerequisites
*   Python 3.12+
*   Google Service Account (JSON)
*   AWS Credentials (Secrets Manager)

### Installation
```bash
git clone https://github.com/MiltonKlun/Pombot_PG_Original.git
cd Pombot_PG_Original
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Running Tests
**Run All Tests:**
```bash
pytest tests/
```

**Run Coverage Report:**
```bash
scripts/run_coverage.bat
```

### 📑 Reports & Logs
*   **Coverage**: Generated in `htmlcov/`
*   **Logs**: System logs in `error.log`

---

## Author
**Milton Klun**  
*QA Automation Engineer & Backend Developer*

<div align="left">
  <a href="https://www.linkedin.com/in/milton-klun/">
    <img src="https://img.shields.io/badge/LinkedIn-Milton%20Klun-blue?style=for-the-badge&logo=linkedin" alt="LinkedIn"/>
  </a>
  <a href="mailto:miltonericklun@gmail.com">
    <img src="https://img.shields.io/badge/Email-Contact%20Me-red?style=for-the-badge&logo=gmail" alt="Email"/>
  </a>
</div>
