#!/usr/bin/env python3
"""
Import employees from attdance.txt file
"""
import os
import sys
import re
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for models import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Base, Employee

def parse_employee_line(line):
    """Parse employee data from fixed-width format"""
    if not line.strip():
        return None
    
    # Split by multiple spaces and clean
    parts = re.split(r'\s{2,}', line.strip())
    if len(parts) < 3:
        return None
    
    # Extract user_id (AC No.)
    user_id = parts[0].strip()
    if not user_id or not user_id.isdigit() and user_id != '3':
        return None
    
    # Extract name
    name = parts[1].strip() if len(parts) > 1 else ""
    if not name or name in ['No.', 'Name']:
        return None
    
    # Extract department (always seems to be "OUR COMPANY")
    department = "OUR COMPANY"
    
    # Extract position/role from the data
    position = "User"  # Default
    if len(parts) >= 4:
        for part in parts[2:]:
            if "Suppervisor" in part or "Supervisor" in part:
                position = "Supervisor"
                break
            elif "User" in part:
                position = "User"
                break
    
    return {
        'user_id': str(user_id).zfill(2),  # Pad with zero if needed
        'name': name,
        'department': department,
        'position': position
    }

def import_employees_from_file(file_path):
    """Import employees from attdance.txt"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    # Create database session
    database_url = os.getenv("DATABASE_URL", "postgresql://adms_user:adms_password@localhost:5432/adms_db")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print(f"Reading employee data from: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        employees_added = 0
        employees_updated = 0
        
        for line_num, line in enumerate(lines, 1):
            if line_num <= 2:  # Skip header lines
                continue
                
            employee_data = parse_employee_line(line)
            if not employee_data:
                continue
            
            print(f"Processing: {employee_data}")
            
            # Check if employee exists
            existing = session.query(Employee).filter(
                Employee.user_id == employee_data['user_id']
            ).first()
            
            if existing:
                # Update existing employee
                existing.name = employee_data['name']
                existing.department = employee_data['department']
                existing.position = employee_data['position']
                existing.updated_at = datetime.utcnow()
                employees_updated += 1
                print(f"  ✅ Updated: {employee_data['name']} (ID: {employee_data['user_id']})")
            else:
                # Create new employee
                employee = Employee(
                    user_id=employee_data['user_id'],
                    name=employee_data['name'],
                    department=employee_data['department'],
                    position=employee_data['position']
                )
                session.add(employee)
                employees_added += 1
                print(f"  ➕ Added: {employee_data['name']} (ID: {employee_data['user_id']})")
        
        # Commit all changes
        session.commit()
        
        print("\n" + "="*60)
        print(f"📊 Import Summary:")
        print(f"   ➕ Added: {employees_added} employees")
        print(f"   ✅ Updated: {employees_updated} employees")
        print(f"   📋 Total processed: {employees_added + employees_updated} employees")
        print("="*60)
        
        # List all employees
        print("\n📋 Current employees in database:")
        employees = session.query(Employee).filter(Employee.is_active == True).all()
        
        print(f"\n{'ID':<4} {'Name':<15} {'Department':<12} {'Position':<12}")
        print("-" * 50)
        for emp in employees:
            print(f"{emp.user_id:<4} {emp.name:<15} {emp.department:<12} {emp.position:<12}")
            
    except Exception as e:
        print(f"❌ Error importing employees: {e}")
        session.rollback()
    finally:
        session.close()

def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "/app/employee_data.txt"  # Default path in container
    
    import_employees_from_file(file_path)

if __name__ == "__main__":
    main()