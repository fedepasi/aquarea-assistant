#!/usr/bin/env python3
"""
Aquarea Assistant — Image Extraction & Multimodal Embedding Setup
=================================================================
Questo script:
1. Estrae immagini significative dai PDF dei manuali Panasonic
2. Genera embedding multimodali con gemini-embedding-2-preview
3. Carica gli embedding su Pinecone per la ricerca semantica delle immagini

Prerequisiti:
  pip install google-genai pymupdf pinecone

Uso:
  export GEMINI_API_KEY="..."
  export PINECONE_API_KEY="..."
  python scripts/setup_images.py --pdf-dir /path/to/pdfs
"""

import os
import sys
import glob
import time
import json
import argparse
import hashlib
from pathlib import Path

import fitz  # PyMuPDF
from google import genai
from google.genai import types
from pinecone import Pinecone

# Config
EMBEDDING_MODEL = "gemini-embedding-2-preview"
EMBEDDING_DIM = 768  # Use 768 for efficiency (MRL supports this)
PINECONE_INDEX_NAME = "aquarea-images"
MIN_IMAGE_SIZE = 5000  # Minimum image bytes to consider (skip tiny icons)
MIN_IMAGE_DIMENSION = 80  # Minimum width/height in pixels
MAX_IMAGES_PER_PAGE = 5  # Limit images per page
BATCH_SIZE = 20  # Pinecone upsert batch size

# Map of PDF UUIDs to friendly names
DOC_NAMES = {
    "dc5dc2c8": "Istruzioni Operative (IT)",
    "e55f1de8": "Manuale Installazione Interna (IT)",
    "7e0ff8df": "Installation Manual Outdoor (EN)",
    "e834acce": "Service Manual (EN)",
}


def get_doc_name(filepath: str) -> str:
    """Get a friendly document name from the file path."""
    basename = os.path.basename(filepath)
    for key, name in DOC_NAMES.items():
        if key in basename:
            return name
    return basename


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> list[dict]:
    """Extract significant images from a PDF, saving them to output_dir."""
    doc = fitz.open(pdf_path)
    doc_name = get_doc_name(pdf_path)
    doc_id = hashlib.md5(pdf_path.encode()).hexdigest()[:8]
    images = []

    print(f"\n  📄 Processing: {doc_name} ({doc.page_count} pages)")

    for page_num in range(doc.page_count):
        page = doc[page_num]
        page_images = page.get_images(full=True)
        img_count = 0

        for img_idx, img_info in enumerate(page_images):
            if img_count >= MAX_IMAGES_PER_PAGE:
                break

            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            if not base_image or not base_image.get("image"):
                continue

            image_bytes = base_image["image"]
            ext = base_image.get("ext", "png")
            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            # Filter out small/insignificant images
            if len(image_bytes) < MIN_IMAGE_SIZE:
                continue
            if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                continue

            # Save image
            img_filename = f"{doc_id}_p{page_num+1:03d}_img{img_idx+1}.{ext}"
            img_path = os.path.join(output_dir, img_filename)
            with open(img_path, "wb") as f:
                f.write(image_bytes)

            # Extract surrounding text from the page for context
            page_text = page.get_text("text").strip()
            # Truncate to first 500 chars for context
            context_text = page_text[:500] if page_text else ""

            images.append({
                "id": f"{doc_id}_p{page_num+1}_img{img_idx+1}",
                "filename": img_filename,
                "path": img_path,
                "doc_name": doc_name,
                "page": page_num + 1,
                "width": width,
                "height": height,
                "size_bytes": len(image_bytes),
                "ext": ext,
                "context_text": context_text,
                "mime_type": f"image/{ext}" if ext != "jpg" else "image/jpeg",
            })
            img_count += 1

    doc.close()
    print(f"     ✅ Extracted {len(images)} significant images")
    return images


def embed_images(client: genai.Client, images: list[dict]) -> list[dict]:
    """Generate multimodal embeddings for extracted images using gemini-embedding-2-preview."""
    print(f"\n  🧠 Generating embeddings for {len(images)} images...")
    embedded = []
    errors = 0

    for i, img in enumerate(images):
        try:
            # Read image bytes
            with open(img["path"], "rb") as f:
                image_bytes = f.read()

            # Create a combined embedding: image + context text (aggregated)
            parts = [
                types.Part.from_bytes(data=image_bytes, mime_type=img["mime_type"]),
            ]
            # Add context text if available
            if img["context_text"]:
                content = types.Content(
                    parts=[
                        types.Part(text=f"Manual page context: {img['context_text'][:300]}"),
                        types.Part.from_bytes(data=image_bytes, mime_type=img["mime_type"]),
                    ]
                )
            else:
                content = types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type=img["mime_type"]),
                    ]
                )

            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[content],
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )

            if result.embeddings and len(result.embeddings) > 0:
                embedding = result.embeddings[0].values
                img["embedding"] = embedding
                embedded.append(img)

                if (i + 1) % 10 == 0:
                    print(f"     ⏳ Embedded {i+1}/{len(images)}...")

            # Rate limiting: Gemini has rate limits
            time.sleep(0.5)

        except Exception as e:
            errors += 1
            print(f"     ⚠️ Error embedding {img['filename']}: {e}")
            if "RATE_LIMIT" in str(e).upper() or "429" in str(e):
                print("     ⏳ Rate limited, waiting 30s...")
                time.sleep(30)
            else:
                time.sleep(1)

    print(f"     ✅ Successfully embedded {len(embedded)} images ({errors} errors)")
    return embedded


def setup_pinecone(api_key: str, images: list[dict]):
    """Create Pinecone index and upsert image embeddings."""
    pc = Pinecone(api_key=api_key)

    # Check if index exists
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if PINECONE_INDEX_NAME not in existing_indexes:
        print(f"\n  📦 Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec={
                "serverless": {
                    "cloud": "aws",
                    "region": "us-east-1",
                }
            },
        )
        # Wait for index to be ready
        print("     ⏳ Waiting for index to be ready...")
        time.sleep(10)
    else:
        print(f"\n  ♻️ Using existing Pinecone index '{PINECONE_INDEX_NAME}'")

    index = pc.Index(PINECONE_INDEX_NAME)

    # Upsert in batches
    print(f"  📤 Uploading {len(images)} embeddings to Pinecone...")
    vectors = []
    for img in images:
        vectors.append({
            "id": img["id"],
            "values": img["embedding"],
            "metadata": {
                "filename": img["filename"],
                "doc_name": img["doc_name"],
                "page": img["page"],
                "width": img["width"],
                "height": img["height"],
                "context_text": img["context_text"][:200],  # Pinecone metadata limit
            },
        })

    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i : i + BATCH_SIZE]
        index.upsert(vectors=batch)
        print(f"     ✅ Upserted batch {i//BATCH_SIZE + 1}/{(len(vectors)-1)//BATCH_SIZE + 1}")

    # Get index stats
    time.sleep(2)
    stats = index.describe_index_stats()
    print(f"     📊 Index stats: {stats.total_vector_count} vectors total")

    return index


def main():
    parser = argparse.ArgumentParser(description="Setup image embeddings for Aquarea Assistant")
    parser.add_argument("--pdf-dir", default=None, help="Directory with PDFs")
    parser.add_argument("--gemini-key", default=None, help="Gemini API key")
    parser.add_argument("--pinecone-key", default=None, help="Pinecone API key")
    parser.add_argument("--output-dir", default=None, help="Output directory for extracted images")
    args = parser.parse_args()

    # API Keys
    gemini_key = args.gemini_key or os.environ.get("GEMINI_API_KEY")
    pinecone_key = args.pinecone_key or os.environ.get("PINECONE_API_KEY")

    if not gemini_key:
        print("❌ GEMINI_API_KEY not set")
        sys.exit(1)
    if not pinecone_key:
        print("❌ PINECONE_API_KEY not set")
        sys.exit(1)

    # Find PDFs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    if args.pdf_dir:
        pdf_dir = args.pdf_dir
    else:
        for search_dir in [project_dir, os.path.dirname(project_dir)]:
            pdfs = glob.glob(os.path.join(search_dir, "*.pdf"))
            if pdfs:
                pdf_dir = search_dir
                break
        else:
            print("❌ No PDFs found. Use --pdf-dir")
            sys.exit(1)

    pdfs = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    print(f"\n📂 Found {len(pdfs)} PDFs in: {pdf_dir}")

    # Output directory for images
    output_dir = args.output_dir or os.path.join(project_dir, "public", "images")
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 Images will be saved to: {output_dir}")

    # Step 1: Extract images from all PDFs
    print("\n" + "=" * 60)
    print("STEP 1: Extracting images from PDFs")
    print("=" * 60)

    all_images = []
    for pdf in pdfs:
        images = extract_images_from_pdf(pdf, output_dir)
        all_images.extend(images)

    print(f"\n📊 Total images extracted: {len(all_images)}")

    if not all_images:
        print("❌ No images found in PDFs")
        sys.exit(1)

    # Step 2: Generate multimodal embeddings
    print("\n" + "=" * 60)
    print("STEP 2: Generating multimodal embeddings (gemini-embedding-2-preview)")
    print("=" * 60)

    gemini_client = genai.Client(api_key=gemini_key)
    embedded_images = embed_images(gemini_client, all_images)

    if not embedded_images:
        print("❌ No embeddings generated")
        sys.exit(1)

    # Step 3: Upload to Pinecone
    print("\n" + "=" * 60)
    print("STEP 3: Uploading to Pinecone")
    print("=" * 60)

    setup_pinecone(pinecone_key, embedded_images)

    # Save image metadata index (for the web app to reference)
    metadata_path = os.path.join(output_dir, "index.json")
    metadata = [
        {
            "id": img["id"],
            "filename": img["filename"],
            "doc_name": img["doc_name"],
            "page": img["page"],
            "width": img["width"],
            "height": img["height"],
        }
        for img in embedded_images
    ]
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\n📝 Image metadata saved to: {metadata_path}")

    # Print env vars
    print(f"""
{'='*60}
✅ IMAGE SETUP COMPLETATO!
{'='*60}

{len(embedded_images)} immagini estratte, embeddate e caricate su Pinecone.

👉 Aggiungi queste righe al file .env.local:

   PINECONE_API_KEY={pinecone_key}
   PINECONE_INDEX=aquarea-images

Le immagini sono in: {output_dir}

{'='*60}
""")


if __name__ == "__main__":
    main()
