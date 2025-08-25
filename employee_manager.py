#!/usr/bin/env python3
"""
Employee Management Script
Used to add/update employee information for Telegram notifications
"""
import sys
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Employee

def create_session():
    """Create database session"""
    database_url = os.getenv("DATABASE_URL", "postgresql://adms_user:adms_password@localhost:5432/adms_db")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def add_employee(user_id: str, name: str, department: str = None, position: str = None, 
                phone: str = None, email: str = None, telegram_chat_id: str = None):
    """Add or update employee"""
    session = create_session()
    
    try:
        # Check if employee exists
        employee = session.query(Employee).filter(Employee.user_id == user_id).first()
        
        if employee:
            print(f"Updating existing employee: {employee.name}")
            employee.name = name
            employee.department = department
            employee.position = position
            employee.phone = phone
            employee.email = email
            employee.telegram_chat_id = telegram_chat_id
            employee.updated_at = datetime.utcnow()
        else:
            print(f"Adding new employee: {name}")
            employee = Employee(
                user_id=user_id,
                name=name,
                department=department,
                position=position,
                phone=phone,
                email=email,
                telegram_chat_id=telegram_chat_id
            )
            session.add(employee)
        
        session.commit()
        print(f"✅ Employee {name} (ID: {user_id}) saved successfully!")
        return employee
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def list_employees():
    """List all employees"""
    session = create_session()
    
    try:
        employees = session.query(Employee).filter(Employee.is_active == True).all()
        
        if not employees:
            print("No employees found.")
            return
        
        print(f"\n{'ID':<10} {'Name':<20} {'Department':<15} {'Position':<15} {'Telegram':<15}")
        print("-" * 80)
        
        for emp in employees:
            telegram_status = "✅" if emp.telegram_chat_id else "❌"
            print(f"{emp.user_id:<10} {emp.name:<20} {emp.department or 'N/A':<15} {emp.position or 'N/A':<15} {telegram_status:<15}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        session.close()

def delete_employee(user_id: str):
    """Delete employee"""
    session = create_session()
    
    try:
        employee = session.query(Employee).filter(Employee.user_id == user_id).first()
        
        if not employee:
            print(f"Employee with ID {user_id} not found.")
            return
        
        employee.is_active = False
        session.commit()
        print(f"✅ Employee {employee.name} (ID: {user_id}) deactivated!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

def main():
    if len(sys.argv) < 2:
        print("""
Employee Management Tool

Usage:
  python employee_manager.py add <user_id> <name> [department] [position] [phone] [email] [telegram_chat_id]
  python employee_manager.py list
  python employee_manager.py delete <user_id>

Examples:
  python employee_manager.py add "01" "John Doe" "IT" "Developer" "+66812345678" "john@company.com" "123456789"
  python employee_manager.py add "02" "Jane Smith" "HR" "Manager"
  python employee_manager.py list
  python employee_manager.py delete "01"
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "add":
        if len(sys.argv) < 4:
            print("Usage: python employee_manager.py add <user_id> <name> [department] [position] [phone] [email] [telegram_chat_id]")
            return
        
        user_id = sys.argv[2]
        name = sys.argv[3]
        department = sys.argv[4] if len(sys.argv) > 4 else None
        position = sys.argv[5] if len(sys.argv) > 5 else None
        phone = sys.argv[6] if len(sys.argv) > 6 else None
        email = sys.argv[7] if len(sys.argv) > 7 else None
        telegram_chat_id = sys.argv[8] if len(sys.argv) > 8 else None
        
        add_employee(user_id, name, department, position, phone, email, telegram_chat_id)
        
    elif command == "list":
        list_employees()
        
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: python employee_manager.py delete <user_id>")
            return
        
        user_id = sys.argv[2]
        delete_employee(user_id)
        
    else:
        print(f"Unknown command: {command}")
        print("Available commands: add, list, delete")

if __name__ == "__main__":
    main()