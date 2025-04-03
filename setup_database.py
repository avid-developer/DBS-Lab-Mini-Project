#!/usr/bin/env python3
"""
Expense Tracker Database Setup Script

This script sets up the database tables, sequences, triggers, and stored procedures
required by the Expense Tracker application. It is designed to be run once to initialize
the database environment.
"""

import oracledb
import os
import sys
import getpass
import re

# Configuration
DB_USER = "expense_app"
DB_PASSWORD = "test123"
DB_DSN = "localhost:1521/ORCLPDB1"
DB_ADMIN_USER = "SYS"  # Used only if expense_app user needs to be created

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_SQL_PATH = os.path.join(SCRIPT_DIR, "database.sql")

def print_header(message):
    """Print a formatted header message"""
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def create_user_if_needed():
    """Create the expense_app user if it doesn't exist"""
    print_header("Checking if expense_app user exists")
    
    try:
        # Try to connect as expense_app
        print("Trying to connect as expense_app user...")
        conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
        print("✅ Successfully connected as expense_app user")
        conn.close()
        return True
    except oracledb.DatabaseError as e:
        if "ORA-01017" in str(e):  # Invalid username/password
            print("❌ Could not connect as expense_app: Invalid credentials")
            print(f"Please check that the password for {DB_USER} is {DB_PASSWORD}")
            return False
        elif "ORA-12514" in str(e) or "ORA-12505" in str(e):  # Service not found
            print("❌ Could not connect to the database service")
            print(f"Please check that the database service {DB_DSN} is running")
            return False
        else:
            print(f"❌ The expense_app user may not exist: {e}")
            
            # Ask if user wants to create the user
            create_user = input("\nDo you want to create the expense_app user? (y/n): ").lower()
            if create_user == 'y':
                try:
                    admin_password = getpass.getpass("Enter SYS password: ")
                    
                    print("Connecting as SYS to create expense_app user...")
                    sys_conn = oracledb.connect(
                        user=DB_ADMIN_USER, 
                        password=admin_password, 
                        dsn=DB_DSN, 
                        mode=oracledb.AUTH_MODE_SYSDBA
                    )
                    
                    cursor = sys_conn.cursor()
                    print("Creating expense_app user...")
                    
                    # Create the user with appropriate privileges
                    cursor.execute(f"CREATE USER {DB_USER} IDENTIFIED BY {DB_PASSWORD}")
                    cursor.execute(f"GRANT CONNECT, RESOURCE TO {DB_USER}")
                    cursor.execute(f"GRANT UNLIMITED TABLESPACE TO {DB_USER}")
                    
                    sys_conn.commit()
                    cursor.close()
                    sys_conn.close()
                    
                    print("✅ Successfully created expense_app user")
                    return True
                except Exception as e:
                    print(f"❌ Error creating expense_app user: {e}")
                    print("\nPlease run the following SQL commands as a privileged user:")
                    print("------------------------------------------------------")
                    print(f"CREATE USER {DB_USER} IDENTIFIED BY {DB_PASSWORD};")
                    print(f"GRANT CONNECT, RESOURCE TO {DB_USER};")
                    print(f"GRANT UNLIMITED TABLESPACE TO {DB_USER};")
                    print("------------------------------------------------------")
                    return False
            else:
                print("\nPlease run the following SQL commands as a privileged user:")
                print("------------------------------------------------------")
                print(f"CREATE USER {DB_USER} IDENTIFIED BY {DB_PASSWORD};")
                print(f"GRANT CONNECT, RESOURCE TO {DB_USER};")
                print(f"GRANT UNLIMITED TABLESPACE TO {DB_USER};")
                print("------------------------------------------------------")
                print("Then run this script again.")
                return False

def extract_sql_statements(sql_content):
    """
    Extract SQL statements from the content, properly handling PL/SQL blocks
    Returns a list of SQL statements and PL/SQL blocks
    """
    # Convert to Unix line endings for consistent processing
    sql_content = sql_content.replace('\r\n', '\n')
    
    # Initialize variables
    statements = []
    current_statement = []
    in_plsql_block = False
    
    # Process line by line
    for line in sql_content.split('\n'):
        line = line.strip()
        
        # Skip empty lines and full-line comments
        if not line or (line.startswith('--') and not line.startswith('-- PART') and not line.startswith('-- =====')):
            continue
            
        # Check for PL/SQL block start
        if re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION|TRIGGER|PACKAGE|TYPE)', line, re.IGNORECASE):
            # If we were collecting a statement, finish it first
            if current_statement and not in_plsql_block:
                statements.append('\n'.join(current_statement))
                current_statement = []
            
            # Start collecting a new PL/SQL block
            in_plsql_block = True
            current_statement.append(line)
        
        # Check for PL/SQL block end - standalone "/" on a line
        elif line == '/' and in_plsql_block:
            # Add the collected block to statements
            statements.append('\n'.join(current_statement))
            current_statement = []
            in_plsql_block = False
        
        # Handle normal SQL statement end (semicolon)
        elif line.endswith(';') and not in_plsql_block:
            current_statement.append(line[:-1])  # Remove the semicolon
            statements.append('\n'.join(current_statement))
            current_statement = []
        
        # Otherwise, just add to current collection
        else:
            current_statement.append(line)
    
    # Add any remaining statement
    if current_statement:
        statements.append('\n'.join(current_statement))
    
    # Filter out empty statements
    return [stmt for stmt in statements if stmt.strip()]

def setup_database():
    """Set up the database schema and procedures"""
    if not os.path.exists(DATABASE_SQL_PATH):
        print(f"❌ Could not find SQL file: {DATABASE_SQL_PATH}")
        print("Please make sure database.sql exists in the same directory as this script.")
        return False
    
    print_header("Setting up database schema and procedures")
    
    try:
        # Connect as expense_app
        print("Connecting to the database...")
        conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
        cursor = conn.cursor()
        
        # Read the SQL file
        print(f"Reading SQL file: {DATABASE_SQL_PATH}")
        with open(DATABASE_SQL_PATH, 'r') as f:
            sql_content = f.read()
        
        # Extract individual SQL statements, properly handling PL/SQL blocks
        print("Parsing SQL statements...")
        statements = extract_sql_statements(sql_content)
        
        # Execute each statement
        print("Executing SQL statements...")
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements):
            statement = statement.strip()
            if not statement or statement.isspace() or statement.startswith('--'):
                continue
            
            # Special handling for PL/SQL blocks
            is_plsql = re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION|TRIGGER|PACKAGE|TYPE)', 
                                statement, re.IGNORECASE)
            
            try:
                # Execute the statement
                cursor.execute(statement)
                print(f"✅ Successfully executed statement {i+1}")
                success_count += 1
            except oracledb.DatabaseError as e:
                # Some errors are expected, like "object already exists"
                if "ORA-00955" in str(e):  # Name is already used by an existing object
                    print(f"⚠️ Object already exists (this is okay): {e}")
                    success_count += 1
                elif "ORA-04043" in str(e) or "ORA-00942" in str(e):  # Object does not exist
                    print(f"⚠️ Object doesn't exist for drop operation (this is okay): {e}")
                    success_count += 1
                else:
                    print(f"❌ Error executing statement {i+1}: {e}")
                    print(f"Help: https://docs.oracle.com/error-help/db/{str(e).split(':')[0].lower()}/")
                    if is_plsql:
                        print("Statement: PL/SQL block...")
                    else:
                        print(f"Statement: {statement[:100]}...")
                    error_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✅ Database setup completed with {success_count} successful statements")
        if error_count > 0:
            print(f"⚠️ There were {error_count} errors during setup")
            return False
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def main():
    """Main function to run the database setup script"""
    print_header("Expense Tracker Database Setup")
    
    # Step 1: Check/create user
    if not create_user_if_needed():
        print("\n❌ Setup failed: Could not connect or create expense_app user")
        sys.exit(1)
    
    # Step 2: Setup database schema and procedures
    if not setup_database():
        print("\n⚠️ Setup completed with warnings. Some objects may not have been created correctly.")
        print("Please check the error messages above.")
        sys.exit(1)
    
    print("\n✅ Database setup completed successfully!")
    print("\nYou can now run the application: python app.py")

if __name__ == "__main__":
    main()