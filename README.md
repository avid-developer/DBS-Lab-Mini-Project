# Expense Tracker Application

A comprehensive personal expense tracking application with budget management, spending alerts, and reporting capabilities. Built with Flask and Oracle Database.

## Features

- **User Authentication**: Register and login to keep your expenses private
- **Expense Management**: Add, categorize, and track your expenses
- **Budget Management**: Set spending limits per category or overall
- **Spending Alerts**: Get notified when you exceed your budget limits
- **Reports and Analytics**: View monthly spending summaries and track spending trends
- **Category Management**: Customize expense categories to match your needs

## Tech Stack

- **Backend**: Python with Flask web framework
- **Database**: Oracle Database (using oracledb Python driver)
- **Frontend**: HTML, CSS, JavaScript (with Bootstrap for styling)
- **Visualization**: Chart.js for expense trend visualization

## Prerequisites

- Python 3.6 or higher
- Oracle Database (tested with Oracle 19c)
- Oracle Instant Client libraries (required for oracledb)

## Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/expense-tracker.git
cd expense-tracker
```

2. **Install Python dependencies**

```bash
pip install flask oracledb
```

3. **Configure the database connection**

Edit the database connection settings in `setup_database.py` and `app.py` if necessary. By default, it uses:
- User: `expense_app`
- Password: `test123`
- DSN: `localhost:1521/ORCLPDB1`

4. **Set up the database**

```bash
python setup_database.py
```

This script will:
- Check if the expense_app user exists and create it if needed (requires SYS credentials)
- Create all necessary tables, sequences, triggers, and stored procedures

## Running the Application

```bash
python app.py
```

The application will be available at http://localhost:5000

## Database Schema

The application uses the following database tables:

- **Users**: Store user account information
- **Categories**: Expense categories (customizable per user)
- **Expenses**: Individual expense records with amount, date, and category
- **Expense_Limits**: Budget limits per category or overall
- **Expense_Alerts**: Notifications when budget limits are exceeded

## Project Structure

- `app.py` - The main Flask application
- `database.sql` - Database schema and PL/SQL procedures definition
- `setup_database.py` - Script to set up the database
- `templates/` - HTML templates for the web application
  - `base.html` - Base template with common layout elements
  - `login.html` - Login page
  - `register.html` - User registration page
  - `dashboard.html` - Main dashboard showing expense summary
  - `add_expense.html` - Form to add new expenses
  - `categories.html` - Manage expense categories
  - `budgets.html` - Set and manage budget limits
  - `alerts.html` - View budget limit alerts
  - `monthly_report.html` - Monthly expense summary report
  - `expense_trends.html` - Expense trends visualization

## Usage Guide

1. **Register a new account** at the registration page
2. **Add expense categories** if you need more than the default ones
3. **Set budget limits** for each category or overall spending
4. **Add expenses** as you incur them
5. **View reports** to analyze your spending habits
6. **Check alerts** when you exceed your budget limits

## Development

To modify the application:
- Edit `app.py` to change application logic and routes
- Modify templates in the `templates/` directory to change the user interface
- Update `database.sql` if you need to change the database schema or PL/SQL procedures
- Run `setup_database.py` again after making schema changes# DBS-Lab-Mini-Project
