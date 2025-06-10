import json
from pathlib import Path

from treebeard import Log


def load_products():
    """Load products from JSON file"""
    try:
        data_file = Path(__file__).parent / "data" / "products.json"
        Log.debug("Loading products from file", file_path=str(data_file))

        with open(data_file) as f:
            products = json.load(f)
            Log.info("Products loaded successfully", count=len(products))
            return products
    except Exception as e:
        Log.error("Failed to load products", error=str(e))
        raise


def get_products(category=None, min_price=None):
    """Get filtered products based on category and minimum price"""
    Log.info("Filtering products",
             data={
                 "category": category,
                 "min_price": min_price
             })

    products = load_products()

    if category:
        products = [p for p in products if p["category"] == category]
        Log.debug("Filtered by category",
                  category=category,
                  remaining_count=len(products))

    if min_price is not None:
        products = [p for p in products if p["price"] >= min_price]
        Log.debug("Filtered by price",
                  min_price=min_price,
                  remaining_count=len(products))

    return products


def get_product_by_id(product_id):
    """Get a specific product by ID"""
    Log.info("Looking up product", product_id=product_id)

    products = load_products()
    product_id = str(product_id)  # Convert to string for comparison

    for product in products:
        if str(product["id"]) == product_id:
            Log.debug("Product found", product_id=product_id)
            return product

    Log.warning("Product not found", product_id=product_id)
    return None
