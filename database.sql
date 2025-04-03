-- Expense Tracker Database Schema & Procedures
-- This file contains the database schema (tables, sequences, triggers) 
-- and PL/SQL procedures for the Expense Tracker application.

-- =============================================================================
-- PART 1: DATABASE SCHEMA (TABLES, SEQUENCES, TRIGGERS)
-- =============================================================================

-- Create Users table
CREATE TABLE Users (
    user_id NUMBER PRIMARY KEY,
    name VARCHAR2(100) NOT NULL,
    email VARCHAR2(100) NOT NULL UNIQUE,
    password VARCHAR2(255) NOT NULL
);

-- Create sequence for Users
CREATE SEQUENCE seq_users START WITH 1 INCREMENT BY 1;

-- Create trigger for Users
CREATE OR REPLACE TRIGGER trg_users
BEFORE INSERT ON Users
FOR EACH ROW
WHEN (NEW.user_id IS NULL)
BEGIN
    SELECT seq_users.NEXTVAL INTO :NEW.user_id FROM dual;
END;
/

-- Create Categories table
CREATE TABLE Categories (
    category_id NUMBER PRIMARY KEY,
    user_id NUMBER NOT NULL,
    category_name VARCHAR2(100) NOT NULL,
    description VARCHAR2(255),
    CONSTRAINT fk_user_category FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

-- Create sequence for Categories
CREATE SEQUENCE seq_categories START WITH 1 INCREMENT BY 1;

-- Create trigger for Categories
CREATE OR REPLACE TRIGGER trg_categories
BEFORE INSERT ON Categories
FOR EACH ROW
WHEN (NEW.category_id IS NULL)
BEGIN
    SELECT seq_categories.NEXTVAL INTO :NEW.category_id FROM dual;
END;
/

-- Create Expenses table
CREATE TABLE Expenses (
    expense_id NUMBER PRIMARY KEY,
    user_id NUMBER NOT NULL,
    category_id NUMBER NOT NULL,
    amount NUMBER(10,2) NOT NULL,
    expense_date DATE NOT NULL,
    description VARCHAR2(4000),
    CONSTRAINT fk_user_expense FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_category_expense FOREIGN KEY (category_id) REFERENCES Categories(category_id)
);

-- Create sequence for Expenses
CREATE SEQUENCE seq_expenses START WITH 1 INCREMENT BY 1;

-- Create trigger for Expenses
CREATE OR REPLACE TRIGGER trg_expenses
BEFORE INSERT ON Expenses
FOR EACH ROW
WHEN (NEW.expense_id IS NULL)
BEGIN
    SELECT seq_expenses.NEXTVAL INTO :NEW.expense_id FROM dual;
END;
/

-- Create Expense_Limits table
CREATE TABLE Expense_Limits (
    limit_id NUMBER PRIMARY KEY,
    user_id NUMBER NOT NULL,
    category_id NUMBER,
    limit_amount NUMBER(10,2) NOT NULL,
    period VARCHAR2(20) DEFAULT 'monthly',
    CONSTRAINT fk_user_limit FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_category_limit FOREIGN KEY (category_id) REFERENCES Categories(category_id)
);

-- Create sequence for Expense_Limits
CREATE SEQUENCE seq_limits START WITH 1 INCREMENT BY 1;

-- Create trigger for Expense_Limits
CREATE OR REPLACE TRIGGER trg_limits
BEFORE INSERT ON Expense_Limits
FOR EACH ROW
WHEN (NEW.limit_id IS NULL)
BEGIN
    SELECT seq_limits.NEXTVAL INTO :NEW.limit_id FROM dual;
END;
/

-- Create Expense_Alerts table
CREATE TABLE Expense_Alerts (
    alert_id NUMBER PRIMARY KEY,
    user_id NUMBER NOT NULL,
    expense_id NUMBER NOT NULL,
    alert_date DATE DEFAULT SYSDATE,
    limit_amount NUMBER(10,2) NOT NULL,
    is_read NUMBER(1) DEFAULT 0,
    CONSTRAINT fk_user_alert FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_expense_alert FOREIGN KEY (expense_id) REFERENCES Expenses(expense_id)
);

-- Create sequence for Expense_Alerts
CREATE SEQUENCE seq_alerts START WITH 1 INCREMENT BY 1;

-- Create trigger for Expense_Alerts
CREATE OR REPLACE TRIGGER trg_alerts
BEFORE INSERT ON Expense_Alerts
FOR EACH ROW
WHEN (NEW.alert_id IS NULL)
BEGIN
    SELECT seq_alerts.NEXTVAL INTO :NEW.alert_id FROM dual;
END;
/

-- =============================================================================
-- PART 2: PL/SQL PROCEDURES AND FUNCTIONS
-- =============================================================================

-- Procedure to check if an expense exceeds a defined limit
CREATE OR REPLACE PROCEDURE check_expense_limit(
    p_user_id IN NUMBER,
    p_category_id IN NUMBER,
    p_amount IN NUMBER,
    p_expense_date IN DATE,
    p_limit_exceeded OUT NUMBER,
    p_limit_amount OUT NUMBER
) AS
    v_month_expenses NUMBER := 0;
    v_limit_amount NUMBER := 0;
    v_period VARCHAR2(20) := 'monthly';
    v_start_date DATE;
    v_end_date DATE;
    v_limit_exists NUMBER := 0;
BEGIN
    -- Initialize output parameters
    p_limit_exceeded := 0;
    p_limit_amount := 0;
    
    -- First check if category-specific limit exists
    SELECT COUNT(*) INTO v_limit_exists
    FROM Expense_Limits
    WHERE user_id = p_user_id 
    AND category_id = p_category_id;
    
    -- Only proceed if a limit exists for this category
    IF v_limit_exists > 0 THEN
        SELECT NVL(limit_amount, 0), NVL(period, 'monthly')
        INTO v_limit_amount, v_period
        FROM Expense_Limits
        WHERE user_id = p_user_id 
        AND category_id = p_category_id
        AND ROWNUM = 1;
        
        IF v_limit_amount > 0 THEN
            -- Determine period dates based on expense date
            IF v_period = 'monthly' THEN
                v_start_date := TRUNC(p_expense_date, 'MM');
                v_end_date := LAST_DAY(p_expense_date);
            ELSIF v_period = 'weekly' THEN
                v_start_date := TRUNC(p_expense_date, 'IW');
                v_end_date := v_start_date + 6;
            ELSIF v_period = 'daily' THEN
                v_start_date := TRUNC(p_expense_date);
                v_end_date := v_start_date;
            END IF;
            
            -- Get total expenses for this category in the period
            SELECT NVL(SUM(amount), 0) INTO v_month_expenses
            FROM Expenses
            WHERE user_id = p_user_id
            AND category_id = p_category_id
            AND expense_date BETWEEN v_start_date AND v_end_date;
            
            -- Check if this new expense will exceed the limit
            IF (v_month_expenses + p_amount) > v_limit_amount THEN
                p_limit_exceeded := 1;
                p_limit_amount := v_limit_amount;
                RETURN;
            END IF;
        END IF;
    END IF;
    
    -- Check if overall limit exists
    SELECT COUNT(*) INTO v_limit_exists
    FROM Expense_Limits
    WHERE user_id = p_user_id 
    AND category_id IS NULL;
    
    -- Then check overall limit if no category-specific limit was exceeded
    IF v_limit_exists > 0 THEN
        SELECT NVL(limit_amount, 0), NVL(period, 'monthly')
        INTO v_limit_amount, v_period
        FROM Expense_Limits
        WHERE user_id = p_user_id 
        AND category_id IS NULL
        AND ROWNUM = 1;
        
        IF v_limit_amount > 0 THEN
            -- Determine period dates
            IF v_period = 'monthly' THEN
                v_start_date := TRUNC(p_expense_date, 'MM');
                v_end_date := LAST_DAY(p_expense_date);
            ELSIF v_period = 'weekly' THEN
                v_start_date := TRUNC(p_expense_date, 'IW');
                v_end_date := v_start_date + 6;
            ELSIF v_period = 'daily' THEN
                v_start_date := TRUNC(p_expense_date);
                v_end_date := v_start_date;
            END IF;
            
            -- Get total expenses for all categories in the period
            SELECT NVL(SUM(amount), 0) INTO v_month_expenses
            FROM Expenses
            WHERE user_id = p_user_id
            AND expense_date BETWEEN v_start_date AND v_end_date;
            
            -- Check if this new expense will exceed the overall limit
            IF (v_month_expenses + p_amount) > v_limit_amount THEN
                p_limit_exceeded := 1;
                p_limit_amount := v_limit_amount;
            END IF;
        END IF;
    END IF;
END;
/

-- Procedure to add expense and check limits
CREATE OR REPLACE PROCEDURE add_expense_with_limit_check(
    p_user_id IN NUMBER,
    p_category_id IN NUMBER,
    p_amount IN NUMBER,
    p_expense_date IN DATE,
    p_description IN VARCHAR2,
    p_limit_exceeded OUT NUMBER,
    p_limit_amount OUT NUMBER,
    p_expense_id OUT NUMBER
) AS
BEGIN
    -- First check if expense would exceed any limits
    check_expense_limit(
        p_user_id, 
        p_category_id, 
        p_amount, 
        p_expense_date, 
        p_limit_exceeded, 
        p_limit_amount
    );
    
    -- Generate a new expense_id
    SELECT seq_expenses.NEXTVAL INTO p_expense_id FROM dual;
    
    -- Insert the expense
    INSERT INTO Expenses (
        expense_id,
        user_id,
        category_id,
        amount,
        expense_date,
        description
    ) VALUES (
        p_expense_id,
        p_user_id,
        p_category_id,
        p_amount,
        p_expense_date,
        p_description
    );
END;
/

-- Procedure to create an alert when a limit is exceeded
CREATE OR REPLACE PROCEDURE create_limit_alert(
    p_user_id IN NUMBER,
    p_expense_id IN NUMBER,
    p_limit_amount IN NUMBER
) AS
BEGIN
    INSERT INTO Expense_Alerts (
        user_id,
        expense_id,
        limit_amount
    ) VALUES (
        p_user_id,
        p_expense_id,
        p_limit_amount
    );
END;
/

-- Function to get monthly summary for a user
CREATE OR REPLACE FUNCTION get_monthly_summary(
    p_user_id IN NUMBER,
    p_month IN NUMBER,
    p_year IN NUMBER
) RETURN SYS_REFCURSOR AS
    v_cursor SYS_REFCURSOR;
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    -- Calculate start and end dates
    v_start_date := TO_DATE(p_year || '-' || p_month || '-01', 'YYYY-MM-DD');
    v_end_date := LAST_DAY(v_start_date);
    
    OPEN v_cursor FOR
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
                      AND e.user_id = p_user_id 
                      AND e.expense_date BETWEEN v_start_date AND v_end_date
        WHERE 
            c.user_id = p_user_id
        GROUP BY 
            c.category_name
        ORDER BY 
            total_amount DESC;
    
    RETURN v_cursor;
END;
/

-- Function to get expense trends
CREATE OR REPLACE FUNCTION get_expense_trends(
    p_user_id IN NUMBER,
    p_months IN NUMBER
) RETURN SYS_REFCURSOR AS
    v_cursor SYS_REFCURSOR;
    v_end_date DATE := LAST_DAY(TRUNC(SYSDATE));
    v_start_date DATE := ADD_MONTHS(TRUNC(v_end_date, 'MM'), -p_months+1);
BEGIN
    OPEN v_cursor FOR
        SELECT 
            TO_CHAR(TRUNC(e.expense_date, 'MM'), 'YYYY-MM') as month,
            c.category_name,
            SUM(e.amount) as total_amount
        FROM 
            Expenses e
        JOIN 
            Categories c ON e.category_id = c.category_id
        WHERE 
            e.user_id = p_user_id
            AND e.expense_date BETWEEN v_start_date AND v_end_date
        GROUP BY 
            TO_CHAR(TRUNC(e.expense_date, 'MM'), 'YYYY-MM'),
            c.category_name
        ORDER BY 
            month, c.category_name;
    
    RETURN v_cursor;
END;
/