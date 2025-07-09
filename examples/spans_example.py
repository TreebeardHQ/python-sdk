"""
Example demonstrating OpenTelemetry spans with Treebeard.
"""
import time
from treebeardhq import Treebeard, start_span, end_span, span_context, SpanKind, SpanStatus, SpanStatusCode

# Initialize Treebeard
Treebeard.init(
    project_name="spans-example",
    api_key="your-api-key-here",  # Replace with your actual API key
    endpoint="https://api.treebeardhq.com/logs/batch"
)

def example_manual_spans():
    """Example using manual span start/end."""
    print("=== Manual Span Example ===")
    
    # Start a root span
    root_span = start_span("main_operation", kind=SpanKind.SERVER)
    root_span.set_attribute("user.id", "12345")
    root_span.set_attribute("request.method", "GET")
    
    time.sleep(0.1)  # Simulate some work
    
    # Start a child span
    child_span = start_span("database_query", kind=SpanKind.CLIENT)
    child_span.set_attribute("db.statement", "SELECT * FROM users")
    child_span.add_event("query_started", {"query.id": "abc123"})
    
    time.sleep(0.05)  # Simulate database work
    
    # End child span
    end_span(child_span, SpanStatus(SpanStatusCode.OK))
    
    # Add event to root span
    root_span.add_event("processing_complete")
    
    # End root span
    end_span(root_span, SpanStatus(SpanStatusCode.OK))


def example_context_manager():
    """Example using span context manager."""
    print("=== Context Manager Example ===")
    
    with span_context("web_request", kind=SpanKind.SERVER) as span:
        span.set_attribute("http.method", "POST")
        span.set_attribute("http.url", "/api/users")
        
        # Simulate some processing
        time.sleep(0.05)
        
        with span_context("validate_input", kind=SpanKind.INTERNAL) as validation_span:
            validation_span.set_attribute("validation.rules", "required_fields")
            time.sleep(0.02)
        
        with span_context("save_to_database", kind=SpanKind.CLIENT) as db_span:
            db_span.set_attribute("db.operation", "INSERT")
            db_span.set_attribute("db.table", "users")
            time.sleep(0.03)


def example_with_error():
    """Example showing error handling in spans."""
    print("=== Error Handling Example ===")
    
    try:
        with span_context("risky_operation") as span:
            span.set_attribute("operation.type", "file_processing")
            
            # Simulate an error
            raise ValueError("Something went wrong!")
    except ValueError as e:
        print(f"Caught error: {e}")
        # The span will automatically be marked with ERROR status


def example_nested_operations():
    """Example showing nested operations."""
    print("=== Nested Operations Example ===")
    
    with span_context("order_processing", SpanKind.SERVER) as order_span:
        order_span.set_attribute("order.id", "order-123")
        order_span.set_attribute("customer.id", "customer-456")
        
        # Validate order
        with span_context("validate_order") as validate_span:
            validate_span.set_attribute("validation.step", "inventory_check")
            time.sleep(0.01)
        
        # Process payment
        with span_context("process_payment", SpanKind.CLIENT) as payment_span:
            payment_span.set_attribute("payment.method", "credit_card")
            payment_span.set_attribute("payment.amount", "99.99")
            
            # Payment processing steps
            with span_context("charge_card") as charge_span:
                charge_span.set_attribute("card.last4", "1234")
                time.sleep(0.02)
        
        # Ship order
        with span_context("ship_order") as ship_span:
            ship_span.set_attribute("shipping.carrier", "UPS")
            ship_span.set_attribute("shipping.tracking", "1Z999AA1234567890")
            time.sleep(0.01)


if __name__ == "__main__":
    # Run examples
    example_manual_spans()
    example_context_manager()
    example_with_error()
    example_nested_operations()
    
    print("\n=== Flushing spans ===")
    # Manually flush to ensure all spans are sent
    instance = Treebeard()
    span_count = instance.flush_spans()
    print(f"Flushed {span_count} spans to Treebeard")
    
    print("Examples complete! Check your Treebeard dashboard to see the spans.")