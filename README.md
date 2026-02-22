# Pombot - Finance & Store Management Bot

<br>

<div align="center">
  <img src="pg_logo.png" alt="PG Original Logo" width="300"/>
  <br>
  <br>
  <h2>Automated Sales, Expenses & Inventory Management System for <a href="https://www.pgoriginal.com/">pgoriginal.com</a>.</h2>
</div>


<div align="center">
  <a href="https://www.pgoriginal.com/">
    <img src="https://img.shields.io/badge/Client-PG%20Original-000?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Website"/>
  </a>
  <a href="https://www.instagram.com/pgoriginalind/">
    <img src="https://img.shields.io/badge/Instagram-@pgoriginalind-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram"/>
  </a>
</div>

---

<div align="center">
  <img src="https://img.shields.io/badge/Status-Complete-success" alt="Status"/>
  <img src="https://img.shields.io/badge/Tests-Passing-green" alt="Tests"/>
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
│   ├── sheets_connectio... #    - Database
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
*QA Automation Engineer | Backend Developer*

<div align="left">
  <a href="https://www.linkedin.com/in/milton-klun/"><img src="https://img.shields.io/badge/LINKEDIN-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn"/></a><a href="mailto:miltonericklun@gmail.com"><img src="https://img.shields.io/badge/EMAIL-D14836?style=for-the-badge" alt="Email"/></a><a href="https://www.miltonklun.com"><img src="https://img.shields.io/badge/PORTFOLIO-000000?style=for-the-badge" alt="Live Site"/></a>
</div>
