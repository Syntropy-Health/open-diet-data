#!/usr/bin/env python3
"""
Generate Embeddings for RAG - USDA Food Data
=============================================================================
Generates vector embeddings from USDA food data for use with RAG systems.

Requirements:
    - OPENAI_API_KEY environment variable (for OpenAI embeddings)
    - Or use --local flag for sentence-transformers (no API key needed)

Usage:
    # With OpenAI (requires OPENAI_API_KEY)
    python scripts/generate-embeddings.py --input output/usda/usda_food_nutrition_data.csv

    # With local embeddings (no API key)
    python scripts/generate-embeddings.py --input output/usda/usda_food_nutrition_data.csv --local

    # Limit rows for testing
    python scripts/generate-embeddings.py --input output/usda/usda_food_nutrition_data.csv --limit 1000
=============================================================================
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    print("Error: pandas required. Install with: pip install pandas")
    sys.exit(1)


def create_food_text(row: pd.Series) -> str:
    """Create searchable text from food row."""
    parts = []

    # Food name and description
    if pd.notna(row.get('food_description')):
        parts.append(row['food_description'])

    if pd.notna(row.get('food_common_name')):
        parts.append(f"Also known as: {row['food_common_name']}")

    if pd.notna(row.get('category')):
        parts.append(f"Category: {row['category']}")

    if pd.notna(row.get('brand_name')):
        parts.append(f"Brand: {row['brand_name']}")

    # Key nutrients
    nutrients = []
    nutrient_cols = [
        ('protein', 'protein'),
        ('total_lipid_fat', 'fat'),
        ('carbohydrate_by_difference', 'carbs'),
        ('calcium_ca', 'calcium'),
        ('iron_fe', 'iron'),
        ('magnesium_mg', 'magnesium'),
        ('vitamin_c_total_ascorbic_acid', 'vitamin C'),
        ('vitamin_d3_cholecalciferol', 'vitamin D'),
        ('vitamin_b12', 'vitamin B12'),
    ]

    for col, name in nutrient_cols:
        if col in row and pd.notna(row[col]) and row[col] > 0:
            nutrients.append(f"{name}: {row[col]:.2f}g/100g")

    if nutrients:
        parts.append("Nutrients per 100g: " + ", ".join(nutrients[:5]))

    return " | ".join(parts)


def generate_openai_embeddings(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Generate embeddings using OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai library required. Install with: pip install openai")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("\nTo set it:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        print("\nGet your API key from: https://platform.openai.com/api-keys")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    embeddings = []

    print(f"Generating embeddings for {len(texts)} texts...")
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        batch_embeddings = [item.embedding for item in response.data]
        embeddings.extend(batch_embeddings)
        print(f"  Processed {min(i + batch_size, len(texts))}/{len(texts)}")

    return embeddings


def generate_local_embeddings(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Generate embeddings using local sentence-transformers model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("Error: sentence-transformers required for local embeddings")
        print("Install with: pip install sentence-transformers")
        sys.exit(1)

    print("Loading local embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    print(f"Generating embeddings for {len(texts)} texts...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    return embeddings.tolist()


def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings from USDA food data for RAG"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to USDA CSV file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path for embeddings (default: output/embeddings/)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local sentence-transformers instead of OpenAI"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        help="Limit number of rows to process (for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for embedding generation"
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    # Set output path
    output_dir = args.output or "output/embeddings"
    os.makedirs(output_dir, exist_ok=True)

    # Load data
    print(f"Loading data from {args.input}...")
    df = pd.read_csv(args.input)

    if args.limit:
        df = df.head(args.limit)
        print(f"Limited to {args.limit} rows")

    print(f"Loaded {len(df)} food items")

    # Create text for embedding
    print("Creating searchable text for each food item...")
    texts = df.apply(create_food_text, axis=1).tolist()

    # Generate embeddings
    if args.local:
        print("\nUsing local embeddings (sentence-transformers)")
        embeddings = generate_local_embeddings(texts, args.batch_size)
        model_name = "all-MiniLM-L6-v2"
    else:
        print("\nUsing OpenAI embeddings (text-embedding-3-small)")
        embeddings = generate_openai_embeddings(texts, args.batch_size)
        model_name = "text-embedding-3-small"

    # Save embeddings
    output_file = os.path.join(output_dir, "usda_embeddings.json")
    print(f"\nSaving embeddings to {output_file}...")

    data = {
        "model": model_name,
        "count": len(embeddings),
        "dimension": len(embeddings[0]) if embeddings else 0,
        "items": [
            {
                "fdc_id": str(row.get('fdc_id', i)),
                "text": texts[i],
                "embedding": embeddings[i]
            }
            for i, (_, row) in enumerate(df.iterrows())
        ]
    }

    with open(output_file, 'w') as f:
        json.dump(data, f)

    file_size = os.path.getsize(output_file) / (1024 * 1024)
    print(f"\nEmbeddings saved: {output_file} ({file_size:.1f} MB)")
    print(f"  Model: {model_name}")
    print(f"  Items: {len(embeddings)}")
    print(f"  Dimensions: {len(embeddings[0]) if embeddings else 0}")


if __name__ == "__main__":
    main()
