# ZKTeco ADMS Server - Code Review Guidelines

## 🎯 Overview

This document provides comprehensive guidelines for code reviews to maintain code quality, consistency, and architectural integrity of the ZKTeco ADMS Server.

## 📋 Review Checklist

### ✅ Architecture & Design

#### Service Architecture
- [ ] New code follows dependency injection patterns
- [ ] Services maintain single responsibility principle
- [ ] Dependencies are properly injected, not hardcoded
- [ ] Event-driven patterns used where appropriate
- [ ] No direct service-to-service coupling

#### Event System
- [ ] Events are type-safe with proper dataclasses
- [ ] Event handlers are async when possible
- [ ] Events publish through EventBus, not direct calls
- [ ] Event names follow naming conventions

#### Background Tasks
- [ ] Long-running operations use FastAPI BackgroundTasks
- [ ] Background tasks have proper error handling
- [ ] Database sessions properly managed in background tasks
- [ ] Sync wrappers properly handle async operations

### ✅ Code Quality

#### Python Standards
- [ ] Code follows PEP 8 style guidelines
- [ ] Type hints used for all function parameters and returns
- [ ] Docstrings provided for all public methods
- [ ] Imports organized and unused imports removed
- [ ] No unused variables or dead code

#### Error Handling
- [ ] Exceptions caught at appropriate levels
- [ ] Error messages are informative and actionable
- [ ] Database transactions handle rollbacks properly
- [ ] External API calls have timeout and retry logic
- [ ] Critical operations log errors with context

#### Logging
- [ ] Appropriate log levels used (DEBUG, INFO, WARNING, ERROR)
- [ ] Log messages provide sufficient context
- [ ] No sensitive data in logs (passwords, tokens)
- [ ] Performance-critical operations logged with timing
- [ ] Structured logging with consistent format

### ✅ Security

#### Authentication & Authorization
- [ ] COMM_KEY validation implemented where required
- [ ] No hardcoded secrets or credentials
- [ ] Environment variables used for configuration
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention verified

#### Data Protection
- [ ] User data handling follows privacy principles
- [ ] File uploads validated and sanitized
- [ ] Photo storage permissions properly configured
- [ ] Database queries use parameterized statements
- [ ] Sensitive logs filtered or redacted

### ✅ Database

#### Schema Design
- [ ] Database migrations provided for schema changes
- [ ] Indexes created for frequently queried columns
- [ ] Foreign key relationships properly defined
- [ ] Data types appropriate for use case
- [ ] No N+1 query problems introduced

#### Query Optimization
- [ ] Efficient queries with appropriate filters
- [ ] Batch operations for bulk data processing
- [ ] Connection pooling utilized properly
- [ ] Database sessions closed in finally blocks
- [ ] Transactions scoped appropriately

### ✅ Testing

#### Unit Tests
- [ ] New functions have corresponding unit tests
- [ ] Tests cover happy path and error conditions
- [ ] Mock external dependencies properly
- [ ] Test data cleanup implemented
- [ ] Edge cases and boundary conditions tested

#### Integration Tests
- [ ] API endpoints tested end-to-end
- [ ] Database integration tested
- [ ] Event system integration verified
- [ ] Background task processing tested
- [ ] Error scenarios covered

### ✅ Performance

#### Efficiency
- [ ] No unnecessary database queries
- [ ] Async/await used for I/O operations
- [ ] Large datasets processed in batches
- [ ] Memory usage optimized
- [ ] CPU-intensive operations optimized

#### Scalability
- [ ] Code supports concurrent processing
- [ ] No global state modifications
- [ ] Thread-safe operations where required
- [ ] Resource cleanup implemented
- [ ] Graceful degradation considered

## 🔍 Review Process

### 1. Pre-Review (Author)

#### Self-Review Checklist
```markdown
- [ ] Code compiles and runs without errors
- [ ] All tests pass locally
- [ ] Documentation updated if needed
- [ ] Breaking changes documented
- [ ] Performance impact assessed
```

#### Code Preparation
- Ensure commit messages are descriptive
- Split large changes into logical commits
- Include context in pull request description
- Reference related issues or tickets
- Add screenshots for UI changes

### 2. Review Process (Reviewer)

#### Review Order
1. **Architecture Review** - Check design patterns
2. **Security Review** - Identify security concerns
3. **Code Quality** - Style, structure, clarity
4. **Testing** - Coverage and quality
5. **Performance** - Efficiency considerations

#### Review Comments
```markdown
# Good Comment Examples:

**Suggestion:** Consider using dependency injection here instead of direct import
**Security:** This endpoint needs authentication validation
**Performance:** This query could benefit from an index on `timestamp`
**Bug:** This could cause a race condition in concurrent scenarios
**Style:** Consider extracting this logic into a separate method

# Comment Categories:
- **Must Fix:** Blocking issues (security, bugs)
- **Should Fix:** Important improvements (performance, maintainability)  
- **Consider:** Optional suggestions (style, optimization)
- **Nitpick:** Minor style/formatting issues
```

### 3. Post-Review Actions

#### Author Responsibilities
- Address all "Must Fix" comments
- Respond to feedback with explanations or changes
- Update tests if logic changes
- Verify all reviewer concerns resolved
- Request re-review if significant changes made

#### Reviewer Responsibilities
- Re-review changes after author updates
- Approve when all concerns addressed
- Provide constructive feedback
- Explain reasoning behind suggestions
- Help author understand best practices

## 📚 Service-Specific Guidelines

### NotificationService
```python
# ✅ Good: Dependency injection
class NotificationService:
    def __init__(self, telegram_notifier: TelegramNotifier):
        self.telegram_notifier = telegram_notifier

# ❌ Bad: Direct instantiation
class NotificationService:
    def __init__(self):
        self.telegram_notifier = TelegramNotifier()
```

### Event Handlers
```python
# ✅ Good: Type-safe event handling
async def handle_photo_uploaded_event(self, event: PhotoUploadedEvent):
    if not isinstance(event, PhotoUploadedEvent):
        return
    # Process event...

# ❌ Bad: Untyped event handling
async def handle_event(self, event):
    # Process event...
```

### Background Tasks
```python
# ✅ Good: Proper session management
def sync_wrapper(self, data):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        db = SessionLocal()
        loop.run_until_complete(self.async_method(db, data))
    finally:
        db.close()
        loop.close()

# ❌ Bad: Session leaks
def sync_wrapper(self, data):
    db = SessionLocal()  # Never closed
    asyncio.run(self.async_method(db, data))
```

### Database Operations
```python
# ✅ Good: Parameterized queries
def get_attendance(user_id: str, date: datetime):
    return db.query(AttendanceRecord).filter(
        AttendanceRecord.user_id == user_id,
        AttendanceRecord.timestamp >= date
    ).all()

# ❌ Bad: String formatting
def get_attendance(user_id: str, date: str):
    query = f"SELECT * FROM attendance WHERE user_id = '{user_id}'"
    return db.execute(query)
```

## 🚀 Performance Guidelines

### Database Queries
```python
# ✅ Good: Efficient loading
def get_recent_attendance(limit: int = 100):
    return db.query(AttendanceRecord)\
             .options(joinedload(AttendanceRecord.device))\
             .order_by(AttendanceRecord.timestamp.desc())\
             .limit(limit)\
             .all()

# ❌ Bad: N+1 queries
def get_recent_attendance():
    records = db.query(AttendanceRecord).all()
    for record in records:
        device = record.device  # Triggers individual query
```

### Async Operations
```python
# ✅ Good: Proper async usage
async def process_multiple_records(records):
    tasks = [process_record(record) for record in records]
    await asyncio.gather(*tasks)

# ❌ Bad: Blocking async
async def process_multiple_records(records):
    for record in records:
        await process_record(record)  # Sequential processing
```

## 🔧 Common Patterns

### Service Method Signatures
```python
# ✅ Consistent pattern
async def save_attendance_records(
    self,
    db: Session,
    records: List[Dict[str, Any]], 
    device_serial: str,
    background_tasks: BackgroundTasks
) -> int:
```

### Error Handling Pattern
```python
# ✅ Consistent error handling
try:
    result = await some_operation()
    logger.info(f"Operation completed: {result}")
    return result
except SpecificError as e:
    logger.error(f"Specific error occurred: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error in {operation_name}: {e}")
    # Handle gracefully or re-raise
```

### Event Publishing Pattern
```python
# ✅ Consistent event publishing
async def upload_photo(self, photo_data):
    saved_path = await self.save_photo(photo_data)
    
    event = PhotoUploadedEvent(
        saved_path=saved_path,
        photo_filename=photo_data.filename,
        device_serial=photo_data.device_serial,
        timestamp=datetime.now()
    )
    
    await event_bus.publish_photo_uploaded(event)
    return saved_path
```

## 📖 Documentation Requirements

### Function Documentation
```python
def parse_attlog_data(self, data_text: str) -> List[Dict[str, Any]]:
    """
    Parse ATTLOG data format from ZKTeco devices.
    
    Supports two formats:
    1. ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode
    2. user_id\ttimestamp\tverify_mode\tin_out\tworkcode (direct format)
    
    Args:
        data_text: Raw attendance data from device
        
    Returns:
        List of parsed attendance records with standardized fields
        
    Raises:
        ValueError: If data format is unrecognizable
        
    Example:
        >>> data = "ATTLOG\t001\t2025-08-27 08:30:00\t1\t0\t0"
        >>> result = parse_attlog_data(data)
        >>> result[0]['user_id']
        '001'
    """
```

### Class Documentation
```python
class NotificationService:
    """
    Service for managing attendance notifications and photo matching.
    
    This service handles:
    - Pending notification storage with thread-safe access
    - Event-driven photo matching and notification triggers
    - Timeout management for notifications without photos
    - Integration with Telegram for message delivery
    
    Attributes:
        pending_notifications: Thread-safe dict of pending notifications
        telegram_notifier: Injected Telegram service dependency
        
    Thread Safety:
        All public methods are thread-safe and can be called concurrently.
    """
```

## ⚠️ Common Anti-Patterns to Avoid

### Global State
```python
# ❌ Bad: Global variables
pending_notifications = {}

# ✅ Good: Service state
class NotificationService:
    def __init__(self):
        self.pending_notifications = {}
```

### Direct Service Coupling
```python
# ❌ Bad: Direct coupling
def process_photo():
    notification_service = NotificationService()
    notification_service.trigger_notifications()

# ✅ Good: Event-driven
async def process_photo():
    event = PhotoUploadedEvent(...)
    await event_bus.publish_photo_uploaded(event)
```

### Blocking Operations
```python
# ❌ Bad: Blocking in async context
async def send_notification():
    time.sleep(10)  # Blocks event loop
    return "sent"

# ✅ Good: Non-blocking
async def send_notification():
    await asyncio.sleep(10)  # Non-blocking
    return "sent"
```

This code review guide ensures consistent, high-quality code that maintains the architectural integrity of the ZKTeco ADMS Server.