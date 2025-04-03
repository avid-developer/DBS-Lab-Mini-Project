from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import oracledb
from datetime import datetime, date
import os
import calendar
import json

# Configuration
SECRET_KEY = os.urandom(24)
DB_USER = "expense_app"
DB_PASSWORD = "test123"
DB_DSN = "localhost:1521/ORCLPDB1"

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db_connection():
    """Create and return a database connection"""
    conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
    return conn

# Home/Login Page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, name FROM Users WHERE email = :email AND password = :password', 
                       {'email': email, 'password': password})
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['name'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

# Dashboard: List expenses and summary
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get recent expenses
    cursor.execute('''
        SELECT e.expense_id, e.expense_date, c.category_name, e.amount, e.description 
        FROM Expenses e 
        JOIN Categories c ON e.category_id = c.category_id 
        WHERE e.user_id = :user_id
        ORDER BY e.expense_date DESC
    ''', {'user_id': session['user_id']})
    expenses = cursor.fetchall()
    
    # Get current month total
    today = date.today()
    first_day = date(today.year, today.month, 1)
    last_day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    
    cursor.execute('''
        SELECT NVL(SUM(amount), 0) 
        FROM Expenses 
        WHERE user_id = :user_id 
        AND expense_date BETWEEN :first_day AND :last_day
    ''', {'user_id': session['user_id'], 'first_day': first_day, 'last_day': last_day})
    monthly_total = cursor.fetchone()[0]
    
    # Get category breakdown for current month
    cursor.execute('''
        SELECT c.category_name, NVL(SUM(e.amount), 0) as total
        FROM Categories c
        LEFT JOIN Expenses e ON c.category_id = e.category_id 
                           AND e.expense_date BETWEEN :first_day AND :last_day
        WHERE c.user_id = :user_id
        GROUP BY c.category_name
        ORDER BY total DESC
    ''', {'user_id': session['user_id'], 'first_day': first_day, 'last_day': last_day})
    category_totals = cursor.fetchall()
    
    # Check for unread alerts
    alert_count = 0
    try:
        cursor.execute('''
            SELECT COUNT(*) 
            FROM Expense_Alerts 
            WHERE user_id = :user_id AND is_read = 0
        ''', {'user_id': session['user_id']})
        alert_count = cursor.fetchone()[0]
    except oracledb.DatabaseError as e:
        # Table likely doesn't exist yet
        if 'ORA-00942' in str(e):  # Table or view does not exist
            pass
        else:
            # If it's some other error, re-raise it
            raise
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', 
                          expenses=expenses, 
                          monthly_total=monthly_total,
                          category_totals=category_totals,
                          alert_count=alert_count)

# Add a new expense
@app.route('/add-expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch categories for this user
    cursor.execute('SELECT category_id, category_name FROM Categories WHERE user_id = :user_id', 
                  {'user_id': session['user_id']})
    categories = cursor.fetchall()
    
    if request.method == 'POST':
        category_id = request.form['category_id']
        amount = float(request.form['amount'])
        expense_date = request.form['expense_date']
        description = request.form.get('description', '')
        
        # Use PL/SQL procedure to add expense and check limits
        limit_exceeded = cursor.var(oracledb.NUMBER)
        limit_amount = cursor.var(oracledb.NUMBER)
        expense_id = cursor.var(oracledb.NUMBER)
        
        cursor.callproc('add_expense_with_limit_check', 
                       [session['user_id'], category_id, amount, 
                        datetime.strptime(expense_date, '%Y-%m-%d').date(),
                        description, limit_exceeded, limit_amount, expense_id])
        
        # If limit exceeded, create alert
        if limit_exceeded.getvalue() == 1:
            cursor.callproc('create_limit_alert', 
                           [session['user_id'], expense_id.getvalue(), limit_amount.getvalue()])
            flash(f'Expense added, but it exceeds your budget limit of ${limit_amount.getvalue():.2f}!')
        else:
            flash('Expense added successfully!')
        
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
    
    cursor.close()
    conn.close()
    
    # Pass current date as default for the form
    return render_template('add_expense.html', categories=categories, now=date.today().strftime('%Y-%m-%d'))

# Budget Management
@app.route('/budgets', methods=['GET', 'POST'])
def manage_budgets():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch categories for this user
    cursor.execute('SELECT category_id, category_name FROM Categories WHERE user_id = :user_id', 
                  {'user_id': session['user_id']})
    categories = cursor.fetchall()
    
    # Fetch existing budget limits
    cursor.execute('''
        SELECT l.limit_id, l.category_id, c.category_name, l.limit_amount, l.period 
        FROM Expense_Limits l
        LEFT JOIN Categories c ON l.category_id = c.category_id
        WHERE l.user_id = :user_id
    ''', {'user_id': session['user_id']})
    limits = cursor.fetchall()
    
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        if category_id == "overall":
            category_id = None
        limit_amount = float(request.form['limit_amount'])
        period = request.form.get('period', 'monthly')
        
        # Get the next sequence value for limit_id
        cursor.execute('SELECT seq_limits.NEXTVAL FROM dual')
        next_limit_id = cursor.fetchone()[0]
        
        cursor.execute('''
            INSERT INTO Expense_Limits (limit_id, user_id, category_id, limit_amount, period)
            VALUES (:limit_id, :user_id, :category_id, :limit_amount, :period)
        ''', {
            'limit_id': next_limit_id,
            'user_id': session['user_id'], 
            'category_id': category_id, 
            'limit_amount': limit_amount, 
            'period': period
        })
        
        conn.commit()
        flash('Budget limit added successfully!')
        return redirect(url_for('manage_budgets'))
    
    cursor.close()
    conn.close()
    
    return render_template('budgets.html', categories=categories, limits=limits)

# Delete a budget limit
@app.route('/delete-budget/<int:limit_id>', methods=['POST'])
def delete_budget(limit_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM Expense_Limits
        WHERE limit_id = :limit_id AND user_id = :user_id
    ''', {'limit_id': limit_id, 'user_id': session['user_id']})
    
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Budget limit deleted')
    return redirect(url_for('manage_budgets'))

# Monthly Report
@app.route('/reports/monthly', methods=['GET', 'POST'])
def monthly_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Default to current month
    today = date.today()
    selected_month = request.form.get('month', today.month)
    selected_year = request.form.get('year', today.year)
    
    if request.method == 'POST':
        selected_month = int(request.form.get('month'))
        selected_year = int(request.form.get('year'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get monthly summary using direct SQL query instead of PL/SQL function
    # to avoid potential issues with cursor passing
    first_day = date(int(selected_year), int(selected_month), 1)
    last_day = date(int(selected_year), int(selected_month), 
                   calendar.monthrange(int(selected_year), int(selected_month))[1])
    
    cursor.execute('''
        SELECT 
            c.category_name,
            NVL(SUM(e.amount), 0) as total_amount,
            COUNT(e.expense_id) as transaction_count,
            MIN(e.amount) as min_expense,
            MAX(e.amount) as max_expense,
            NVL(AVG(e.amount), 0) as avg_expense
        FROM 
            Categories c
        LEFT JOIN 
            Expenses e ON c.category_id = e.category_id 
                    AND e.user_id = :user_id 
                    AND e.expense_date BETWEEN :first_day AND :last_day
        WHERE 
            c.user_id = :user_id
        GROUP BY 
            c.category_name
        ORDER BY 
            total_amount DESC
    ''', {'user_id': session['user_id'], 'first_day': first_day, 'last_day': last_day})
    
    summary = []
    for row in cursor:
        summary.append({
            'category': row[0],
            'total': row[1],
            'count': row[2],
            'min': row[3],
            'max': row[4],
            'avg': row[5]
        })
    
    cursor.close()
    conn.close()
    
    return render_template('monthly_report.html', 
                          summary=summary, 
                          month=selected_month,
                          year=selected_year,
                          month_name=calendar.month_name[int(selected_month)])

# Expense Trends
@app.route('/reports/trends')
def expense_trends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    months = request.args.get('months', 6, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the current date for reference
    today = date.today()
    start_date = date(today.year - (1 if today.month <= months else 0), 
                     (today.month - months) % 12 + 1, 1)
    end_date = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    
    # Use direct SQL query instead of PL/SQL function to avoid potential issues
    cursor.execute('''
        SELECT 
            TO_CHAR(TRUNC(e.expense_date, 'MM'), 'YYYY-MM') as month,
            c.category_name,
            SUM(e.amount) as total_amount
        FROM 
            Expenses e
        JOIN 
            Categories c ON e.category_id = c.category_id
        WHERE 
            e.user_id = :user_id
            AND e.expense_date BETWEEN :start_date AND :end_date
        GROUP BY 
            TO_CHAR(TRUNC(e.expense_date, 'MM'), 'YYYY-MM'),
            c.category_name
        ORDER BY 
            month, c.category_name
    ''', {'user_id': session['user_id'], 'start_date': start_date, 'end_date': end_date})
    
    trends_data = []
    for row in cursor:
        trends_data.append({
            'month': row[0],
            'category': row[1],
            'amount': float(row[2])
        })
    
    # Process data to make it suitable for charts
    months = []
    categories = set()
    data_map = {}
    
    for item in trends_data:
        if item['month'] not in months:
            months.append(item['month'])
        categories.add(item['category'])
        
        key = (item['month'], item['category'])
        data_map[key] = item['amount']
    
    # Sort months chronologically
    months.sort()
    categories = sorted(list(categories))
    
    # If we have no data, create some placeholder months based on the selected range
    if not months:
        current_date = start_date
        while current_date <= end_date:
            month_str = current_date.strftime('%Y-%m')
            if month_str not in months:
                months.append(month_str)
            current_date = date(
                current_date.year + (1 if current_date.month == 12 else 0),
                (current_date.month % 12) + 1,
                1
            )
        months.sort()
    
    # Create data for the chart
    chart_data = {
        'labels': months,
        'datasets': []
    }
    
    for category in categories:
        dataset = {
            'label': category,
            'data': [data_map.get((month, category), 0) for month in months]
        }
        chart_data['datasets'].append(dataset)
    
    cursor.close()
    conn.close()
    
    return render_template('expense_trends.html', 
                          chart_data=json.dumps(chart_data),
                          months=months)

# Manage Categories
@app.route('/categories', methods=['GET', 'POST'])
def manage_categories():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        category_name = request.form['category_name']
        description = request.form.get('description', '')
        
        cursor.execute('''
            INSERT INTO Categories (user_id, category_name, description)
            VALUES (:user_id, :category_name, :description)
        ''', {'user_id': session['user_id'], 'category_name': category_name, 'description': description})
        
        conn.commit()
        flash('Category added successfully!')
        return redirect(url_for('manage_categories'))
    
    # Fetch existing categories
    cursor.execute('''
        SELECT category_id, category_name, description
        FROM Categories
        WHERE user_id = :user_id
        ORDER BY category_name
    ''', {'user_id': session['user_id']})
    
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('categories.html', categories=categories)

# View Alerts
@app.route('/alerts')
def view_alerts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.alert_id, a.alert_date, e.amount, c.category_name, a.limit_amount, a.is_read
        FROM Expense_Alerts a
        JOIN Expenses e ON a.expense_id = e.expense_id
        JOIN Categories c ON e.category_id = c.category_id
        WHERE a.user_id = :user_id
        ORDER BY a.alert_date DESC, a.is_read
    ''', {'user_id': session['user_id']})
    
    alerts = cursor.fetchall()
    
    # Mark all as read
    cursor.execute('''
        UPDATE Expense_Alerts
        SET is_read = 1
        WHERE user_id = :user_id AND is_read = 0
    ''', {'user_id': session['user_id']})
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return render_template('alerts.html', alerts=alerts)

# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT COUNT(*) FROM Users WHERE email = :email', {'email': email})
        if cursor.fetchone()[0] > 0:
            flash('Email already registered')
            cursor.close()
            conn.close()
            return render_template('register.html')
        
        # Register the user
        cursor.execute('''
            INSERT INTO Users (name, email, password)
            VALUES (:name, :email, :password)
        ''', {'name': name, 'email': email, 'password': password})
        
        # Get the new user_id
        cursor.execute('SELECT user_id FROM Users WHERE email = :email', {'email': email})
        user_id = cursor.fetchone()[0]
        
        # Create default categories for new user
        default_categories = ['Food', 'Housing', 'Transportation', 'Entertainment', 
                             'Healthcare', 'Personal', 'Education', 'Other']
        for category in default_categories:
            cursor.execute('''
                INSERT INTO Categories (user_id, category_name)
                VALUES (:user_id, :category_name)
            ''', {'user_id': user_id, 'category_name': category})
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API endpoints for AJAX
# Get data for expense chart on dashboard
@app.route('/api/dashboard/chart-data')
def dashboard_chart_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get data for last 6 months
    today = date.today()
    start_date = date(today.year - 1 if today.month <= 6 else today.year, 
                     (today.month - 6) % 12 + 1, 1)
    
    cursor.execute('''
        SELECT TO_CHAR(TRUNC(expense_date, 'MM'), 'YYYY-MM') as month, SUM(amount) as total
        FROM Expenses
        WHERE user_id = :user_id AND expense_date >= :start_date
        GROUP BY TO_CHAR(TRUNC(expense_date, 'MM'), 'YYYY-MM')
        ORDER BY month
    ''', {'user_id': session['user_id'], 'start_date': start_date})
    
    months = []
    totals = []
    
    for row in cursor:
        months.append(row[0])
        totals.append(float(row[1]))
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'labels': months,
        'datasets': [{
            'label': 'Monthly Expenses',
            'data': totals
        }]
    })

if __name__ == '__main__':
    app.run(debug=True)