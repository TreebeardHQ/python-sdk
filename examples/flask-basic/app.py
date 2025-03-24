from flask import Flask, request, jsonify
from treebeard import Treebeard, Log
import utils

app = Flask(__name__)

# Initialize Treebeard
Treebeard.init(
    api_key="",
    endpoint="https://your-logging-endpoint.com/logs"
)


@app.route("/products")
def list_products():
    # Start a trace for this request
    trace_id = Log.start("list-products")

    try:
        category = request.args.get("category")
        min_price = request.args.get("min_price")

        Log.info("Processing product list request",
                 category=category,
                 min_price=min_price)

        products = utils.get_products(
            category=category,
            min_price=float(min_price) if min_price else None
        )

        return jsonify({"products": products})
    except ValueError as e:
        Log.error("Invalid request parameters", error=str(e))
        return jsonify({"error": str(e)}), 400
    finally:
        Log.end()


@app.route("/products/<product_id>")
def get_product(product_id):
    trace_id = Log.start("get-product")

    try:
        Log.info("Fetching product details", product_id=product_id)

        product = utils.get_product_by_id(product_id)
        if product:
            Log.info("Product found", product_id=product_id)
            return jsonify(product)

        Log.warning("Product not found", product_id=product_id)
        return jsonify({"error": "Product not found"}), 404
    except ValueError as e:
        Log.error("Error fetching product", error=str(e))
        return jsonify({"error": str(e)}), 400
    finally:
        Log.end()


if __name__ == "__main__":
    app.run(debug=True)
