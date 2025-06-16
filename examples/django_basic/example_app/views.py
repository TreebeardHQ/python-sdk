from django.http import JsonResponse
from django.shortcuts import render
from treebeardhq.log import Log
import time
import random


def home(request):
    """Home page view that demonstrates basic logging."""
    Log.info("User visited home page")
    return JsonResponse({
        "message": "Welcome to the Treebeard Django Example",
        "status": "success"
    })


def products(request):
    """Products view that demonstrates logging with data."""
    Log.info("User requested products list")
    
    products_data = [
        {"id": 1, "name": "Laptop", "price": 999.99},
        {"id": 2, "name": "Mouse", "price": 29.99},
        {"id": 3, "name": "Keyboard", "price": 79.99},
    ]
    
    Log.info(f"Returning {len(products_data)} products")
    
    return JsonResponse({
        "products": products_data,
        "count": len(products_data)
    })


def slow_operation(request):
    """Slow operation to demonstrate timing and performance logging."""
    Log.info("Starting slow operation")
    
    # Simulate some work
    processing_time = random.uniform(0.5, 2.0)
    time.sleep(processing_time)
    
    Log.info(f"Slow operation completed in {processing_time:.2f} seconds")
    
    return JsonResponse({
        "message": "Operation completed",
        "processing_time": round(processing_time, 2)
    })


def error_example(request):
    """Example endpoint that demonstrates error logging."""
    Log.info("Error example endpoint called")
    
    try:
        # Simulate an error condition
        if random.choice([True, False]):
            raise ValueError("Simulated error for demonstration")
        
        Log.info("No error occurred this time")
        return JsonResponse({"message": "Success - no error this time!"})
        
    except ValueError as e:
        Log.error(f"Caught error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def user_profile(request, user_id):
    """User profile view that demonstrates logging with parameters."""
    Log.info(f"Fetching profile for user {user_id}")
    
    # Simulate user lookup
    if user_id <= 0:
        Log.warning(f"Invalid user ID requested: {user_id}")
        return JsonResponse({"error": "Invalid user ID"}, status=400)
    
    user_data = {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
    }
    
    Log.info(f"Successfully retrieved profile for user {user_id}")
    
    return JsonResponse({"user": user_data})
