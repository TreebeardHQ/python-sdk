# Flask Basic Example

This example demonstrates how to use Treebeard logging in a Flask application, showing logging across multiple levels of the application.

## Setup

1. Create and activate a virtual environment (recommended):
   python -m venv venv
   source venv/bin/activate # On Windows: venv\Scripts\activate

2. Install dependencies:
   pip install -r requirements.txt

   Note: To use the local Treebeard library, add the following to your requirements.txt:
   -e ../..

   This will install the Treebeard package from the parent directory in development mode.

3. Install the local Treebeard library:

   If you encounter an error about missing setup.py when using editable installs,
   create a minimal setup.py file in the root directory with:

   ```python
   from setuptools import setup, find_packages

   setup(
       name="treebeard",
       version="0.1.0",
       packages=find_packages(),
   )
   ```

   Then install in editable mode:
   pip install -e ../..

4. Run the application:
   python app.py

## Usage

The application exposes the following endpoints:

## GET /products

Lists all products with optional filtering

Query parameters:

- category: Filter products by category
- min_price: Filter products by minimum price

Example:
curl "http://localhost:5000/products?category=electronics&min_price=100"

## GET /products/<product_id>

Get details for a specific product

Example:
curl "http://localhost:5000/products/1"
