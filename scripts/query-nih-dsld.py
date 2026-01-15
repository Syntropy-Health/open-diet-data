#!/usr/bin/env python3
"""
NIH Dietary Supplement Label Database (DSLD) - Query Script
=============================================================================
Queries the NIH Office of Dietary Supplements API for supplement information.

API Documentation: https://dsld.od.nih.gov/api-guide
No API key required - public API with rate limits.

Usage:
    python scripts/query-nih-dsld.py --ingredient "vitamin d"
    python scripts/query-nih-dsld.py --product "multivitamin"
    python scripts/query-nih-dsld.py --brand "nature made"
=============================================================================
"""

import argparse
import json
import sys
from typing import Optional
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

# NIH DSLD API Configuration
DSLD_BASE_URL = "https://api.ods.od.nih.gov/dsld/v9"

# API Endpoints (no key required)
ENDPOINTS = {
    "search": "/browse",
    "label": "/label",
    "ingredient": "/ingredient",
}


def search_products(query: str, limit: int = 10) -> dict:
    """Search for supplement products by name."""
    url = f"{DSLD_BASE_URL}/browse"
    params = {
        "name": query,
        "pagesize": limit,
        "page": 1,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_product_label(dsld_id: str) -> dict:
    """Get detailed label information for a specific product."""
    url = f"{DSLD_BASE_URL}/label/{dsld_id}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def search_by_ingredient(ingredient: str, limit: int = 10) -> dict:
    """Search for products containing a specific ingredient."""
    url = f"{DSLD_BASE_URL}/browse"
    params = {
        "ingredient": ingredient,
        "pagesize": limit,
        "page": 1,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_by_brand(brand: str, limit: int = 10) -> dict:
    """Search for products by brand name."""
    url = f"{DSLD_BASE_URL}/browse"
    params = {
        "brandname": brand,
        "pagesize": limit,
        "page": 1,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def format_product(product: dict) -> str:
    """Format a product for display."""
    lines = []
    lines.append(f"  ID: {product.get('dsld_id', 'N/A')}")
    lines.append(f"  Name: {product.get('product_name', 'N/A')}")
    lines.append(f"  Brand: {product.get('brand_name', 'N/A')}")
    lines.append(f"  Type: {product.get('product_type', 'N/A')}")

    if 'serving_size' in product:
        lines.append(f"  Serving: {product['serving_size']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Query NIH Dietary Supplement Label Database (DSLD)"
    )
    parser.add_argument(
        "--product", "-p",
        help="Search for products by name"
    )
    parser.add_argument(
        "--ingredient", "-i",
        help="Search for products containing an ingredient"
    )
    parser.add_argument(
        "--brand", "-b",
        help="Search for products by brand name"
    )
    parser.add_argument(
        "--label", "-l",
        help="Get detailed label by DSLD ID"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Maximum results to return (default: 10)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output raw JSON"
    )

    args = parser.parse_args()

    if not any([args.product, args.ingredient, args.brand, args.label]):
        parser.print_help()
        print("\n" + "=" * 60)
        print("NIH DSLD API Information")
        print("=" * 60)
        print("\nAPI Base URL: https://api.ods.od.nih.gov/dsld/v9")
        print("Documentation: https://dsld.od.nih.gov/api-guide")
        print("Web Interface: https://dsld.od.nih.gov/")
        print("\nNo API key required - public access with rate limits")
        print("\nExample queries:")
        print("  python query-nih-dsld.py --ingredient 'vitamin d' --limit 5")
        print("  python query-nih-dsld.py --product 'fish oil'")
        print("  python query-nih-dsld.py --brand 'nature made'")
        print("  python query-nih-dsld.py --label 123456 --json")
        sys.exit(0)

    try:
        if args.label:
            print(f"Fetching label for DSLD ID: {args.label}")
            result = get_product_label(args.label)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print("\n" + "=" * 60)
                print("Product Label Details")
                print("=" * 60)
                print(json.dumps(result, indent=2))

        elif args.ingredient:
            print(f"Searching for products with ingredient: {args.ingredient}")
            result = search_by_ingredient(args.ingredient, args.limit)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                products = result.get("products", result.get("data", []))
                print(f"\nFound {len(products)} products:\n")
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.get('product_name', 'Unknown')}")
                    print(format_product(product))
                    print()

        elif args.brand:
            print(f"Searching for brand: {args.brand}")
            result = search_by_brand(args.brand, args.limit)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                products = result.get("products", result.get("data", []))
                print(f"\nFound {len(products)} products:\n")
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.get('product_name', 'Unknown')}")
                    print(format_product(product))
                    print()

        elif args.product:
            print(f"Searching for product: {args.product}")
            result = search_products(args.product, args.limit)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                products = result.get("products", result.get("data", []))
                print(f"\nFound {len(products)} products:\n")
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.get('product_name', 'Unknown')}")
                    print(format_product(product))
                    print()

    except requests.exceptions.RequestException as e:
        print(f"Error querying NIH DSLD API: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing API response: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
