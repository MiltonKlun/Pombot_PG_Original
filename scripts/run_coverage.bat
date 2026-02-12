@echo off
echo Running tests and generating HTML coverage report for project files only...
python -m pytest tests/ --cov=handlers --cov=services --cov=lambdas --cov=utils.py --cov=config.py --cov=main.py --cov=sheet.py --cov=constants.py --cov-report=html
echo.
echo Report generated in htmlcov/index.html
start htmlcov/index.html
