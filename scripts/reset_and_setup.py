#!/usr/bin/env python3
"""
Aquarea Assistant — Full Reset & Setup
======================================
1. Estrae le pagine italiane dal PDF outdoor (33-64)
2. Cancella il vecchio File Search Store e indice Pinecone
3. Ricrea File Search Store con i 4 PDF filtrati
4. Estrae immagini dai PDF (migliorato)
5. Embedda ogni immagine con gemini-embedding-2-preview (singola Part.from_bytes)
6. Carica su Pinecone

Uso:
  export GEMINI_API_KEY="..."
  export PINECONE_API_KEY="..."
  python scripts/reset_and_setup.py --pdf-dir /path/to/pdfs
"""

import os
import sys
import glob
import time
import json
import hashlib
import argparse
from pathlib import Path

import fitz  # PyMuPDF
from google import genai
from google.genai import types
from pinecone import Pinecone

# ── Config ──────────────────────────────────────────────
EMBEDDING_MODEL = "gemini-embedding-2-preview"
EMBEDDING_DIM = 768
PINECONE_INDEX_NAME = "aquarea-images"
MIN_IMAGE_SIZE = 3000       # bytes
MIN_IMAGE_DIMENSION = 60    # px
MAX_IMAGES_PER_PAGE = 6
BATCH_SIZE = 20

DOC_CONFIG = {
    "7e0ff8df": {
        "name": "Manuale Installazione Outdoor (IT)",
        "pages": (33, 64),  # 1-indexed, inclusive
    },
    "dc5dc2c8": {
        "name": "Istruzioni Operative (IT)",
        "pages": None,  # tutto
    },
    "e55f1de8": {
        "name": "Manuale Installazione Interna (IT)",
        "pages": None,  # tutto
    },
    "e834acce": {
        "name": "Service Manual (EN)",
        "pages": None,  # tutto
    },
}


def find_doc_config(filepath: str):
    """Match a PDF file to its config entry."""
    basename = os.path.basename(filepath)
    for key, cfg in DOC_CONFIG.items():
        if key in basename:
            return key, cfg
    return None, None


# ── STEP 1: Extract Italian pages from outdoor PDF ─────
def extract_pdf_pages(input_path: str, output_path: str, start_page: int, end_page: int):
    """Extract a range of pages from a PDF (1-indexed, inclusive)."""
    doc = fitz.open(input_path)
    new_doc = fitz.open()
    # fitz uses 0-indexed pages
    for page_num in range(start_page - 1, min(end_page, doc.page_count)):
        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    new_doc.save(output_path)
    new_doc.close()
    doc.close()
    print(f"  Estratte pagine {start_page}-{end_page} → {os.path.basename(output_path)} ({end_page - start_page + 1} pagine)")
    return output_path


# ── STEP 2: Delete old stores ──────────────────────────
def delete_file_search_stores(client):
    """Delete all existing Aquarea file search stores."""
    print("\n  Cercando File Search Stores esistenti...")
    try:
        pager = client.file_search_stores.list(config={"page_size": 50})
        for store in pager:
            if "aquarea" in (store.display_name or "").lower() or "panasonic" in (store.display_name or "").lower():
                print(f"  Cancellando store: {store.name} ({store.display_name})")
                try:
                    client.file_search_stores.delete(name=store.name)
                except Exception as e:
                    print(f"    ⚠️ Errore cancellazione: {e}")
    except Exception as e:
        print(f"  ⚠️ Errore listing stores: {e}")


def delete_pinecone_index(pc):
    """Delete the Pinecone index if it exists."""
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME in existing:
        print(f"  Cancellando indice Pinecone '{PINECONE_INDEX_NAME}'...")
        pc.delete_index(PINECONE_INDEX_NAME)
        print(f"  ✅ Indice cancellato. Attendo propagazione...")
        time.sleep(5)
    else:
        print(f"  Indice Pinecone '{PINECONE_INDEX_NAME}' non esiste, nulla da cancellare.")


# ── STEP 3: Upload PDFs to File Search ─────────────────
def create_file_search_store(client, pdf_paths):
    """Create a new store and upload all PDFs."""
    store = client.file_search_stores.create(
        config={"display_name": "Aquarea Panasonic Manuals v2"}
    )
    store_name = store.name
    print(f"  ✅ Store creato: {store_name}")

    operations = []
    for pdf_path in pdf_paths:
        _, cfg = find_doc_config(pdf_path)
        display_name = cfg["name"] if cfg else os.path.basename(pdf_path)
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        print(f"  📤 Upload: {display_name} ({size_mb:.1f} MB)...")
        try:
            op = client.file_search_stores.upload_to_file_search_store(
                file=pdf_path,
                file_search_store_name=store_name,
                config={"display_name": display_name},
            )
            operations.append((display_name, op))
        except Exception as e:
            print(f"     ❌ Errore: {e}")

    # Wait for indexing
    print("\n  ⏳ Attendo indicizzazione...")
    for display_name, op in operations:
        while not op.done:
            print(f"     ⏳ {display_name}...")
            time.sleep(10)
            op = client.operations.get(op)
        print(f"     ✅ {display_name}: completato")

    return store_name


# ── STEP 4: Extract images (improved) ──────────────────
def extract_images(pdf_path: str, output_dir: str, doc_key: str, doc_name: str, page_offset: int = 0):
    """
    Extract significant images from PDF.
    page_offset: offset to add to page numbers (for sliced PDFs, to report original page numbers)
    """
    doc = fitz.open(pdf_path)
    images = []
    doc_id = doc_key[:8]

    print(f"\n  📄 {doc_name} ({doc.page_count} pagine)")

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        original_page = page_idx + 1 + page_offset
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

            if len(image_bytes) < MIN_IMAGE_SIZE:
                continue
            if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                continue

            # Use png/jpeg only
            if ext not in ("png", "jpeg", "jpg"):
                ext = "png"
            mime = "image/png" if ext == "png" else "image/jpeg"

            img_filename = f"{doc_id}_p{original_page:03d}_img{img_idx+1}.{ext}"
            img_path = os.path.join(output_dir, img_filename)
            with open(img_path, "wb") as f:
                f.write(image_bytes)

            # Page text for context
            page_text = page.get_text("text").strip()[:400]

            images.append({
                "id": f"{doc_id}_p{original_page}_img{img_idx+1}",
                "filename": img_filename,
                "path": img_path,
                "doc_name": doc_name,
                "page": original_page,
                "width": width,
                "height": height,
                "size_bytes": len(image_bytes),
                "mime_type": mime,
                "context_text": page_text,
            })
            img_count += 1

    doc.close()
    print(f"     ✅ {len(images)} immagini estratte")
    return images


# ── STEP 5: Embed images with gemini-embedding-2-preview
def embed_images(client, images):
    """
    Embed each image using gemini-embedding-2-preview.
    Uses Part.from_bytes directly (official method).
    Each image is embedded individually for clean, per-image vectors.
    """
    print(f"\n  🧠 Embedding {len(images)} immagini con {EMBEDDING_MODEL}...")
    embedded = []
    errors = 0

    for i, img in enumerate(images):
        try:
            with open(img["path"], "rb") as f:
                image_bytes = f.read()

            # Embed the image as a single Part (official API method)
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=img["mime_type"],
                    ),
                ],
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIM,
                ),
            )

            if result.embeddings and len(result.embeddings) > 0:
                img["embedding"] = result.embeddings[0].values
                embedded.append(img)

            if (i + 1) % 10 == 0:
                print(f"     ⏳ {i+1}/{len(images)}...")

            # Rate limiting
            time.sleep(0.3)

        except Exception as e:
            errors += 1
            err_str = str(e)
            print(f"     ⚠️ Errore {img['filename']}: {err_str[:100]}")
            if "429" in err_str or "RATE" in err_str.upper():
                print("     ⏳ Rate limit, attendo 30s...")
                time.sleep(30)
            else:
                time.sleep(1)

    print(f"     ✅ {len(embedded)} embeddings generati ({errors} errori)")
    return embedded


# ── STEP 6: Upload to Pinecone ─────────────────────────
def upload_to_pinecone(pc, images):
    """Create fresh Pinecone index and upload embeddings."""
    print(f"\n  📦 Creando indice Pinecone '{PINECONE_INDEX_NAME}'...")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=EMBEDDING_DIM,
        metric="cosine",
        spec={"serverless": {"cloud": "aws", "region": "us-east-1"}},
    )
    print("     ⏳ Attendo che l'indice sia pronto...")
    time.sleep(15)

    index = pc.Index(PINECONE_INDEX_NAME)

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
                "context_text": img["context_text"][:200],
            },
        })

    print(f"  📤 Uploading {len(vectors)} vettori...")
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch)
        print(f"     ✅ Batch {i // BATCH_SIZE + 1}/{(len(vectors) - 1) // BATCH_SIZE + 1}")

    time.sleep(3)
    stats = index.describe_index_stats()
    print(f"     📊 Totale vettori: {stats.total_vector_count}")


# ── MAIN ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", default=None)
    parser.add_argument("--gemini-key", default=None)
    parser.add_argument("--pinecone-key", default=None)
    args = parser.parse_args()

    gemini_key = args.gemini_key or os.environ.get("GEMINI_API_KEY")
    pinecone_key = args.pinecone_key or os.environ.get("PINECONE_API_KEY")

    if not gemini_key:
        print("❌ GEMINI_API_KEY non impostata"); sys.exit(1)
    if not pinecone_key:
        print("❌ PINECONE_API_KEY non impostata"); sys.exit(1)

    # Find PDFs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    if args.pdf_dir:
        pdf_dir = args.pdf_dir
    else:
        for d in [project_dir, os.path.dirname(project_dir)]:
            if glob.glob(os.path.join(d, "*.pdf")):
                pdf_dir = d
                break
        else:
            print("❌ Nessun PDF trovato"); sys.exit(1)

    all_pdfs = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    print(f"\n📂 Trovati {len(all_pdfs)} PDF in: {pdf_dir}")

    # Temp and output dirs
    tmp_dir = os.path.join(project_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    img_dir = os.path.join(project_dir, "public", "images")
    os.makedirs(img_dir, exist_ok=True)

    # Use a fresh subdirectory for images (v2)
    img_dir = os.path.join(img_dir, "v2")
    os.makedirs(img_dir, exist_ok=True)
    print(f"📁 Immagini in: {img_dir}")

    # ── STEP 1: Prepare PDFs ──
    print("\n" + "=" * 60)
    print("STEP 1: Preparazione PDF (estrazione sezioni italiane)")
    print("=" * 60)

    upload_pdfs = []
    image_sources = []  # (pdf_path, doc_key, doc_name, page_offset)

    for pdf in all_pdfs:
        doc_key, cfg = find_doc_config(pdf)
        if not cfg:
            print(f"  ⚠️ PDF non riconosciuto, skippo: {os.path.basename(pdf)}")
            continue

        if cfg["pages"]:
            start, end = cfg["pages"]
            out_path = os.path.join(tmp_dir, f"{doc_key}_it.pdf")
            extract_pdf_pages(pdf, out_path, start, end)
            upload_pdfs.append(out_path)
            image_sources.append((out_path, doc_key, cfg["name"], start - 1))
        else:
            print(f"  ✅ {cfg['name']}: intero")
            upload_pdfs.append(pdf)
            image_sources.append((pdf, doc_key, cfg["name"], 0))

    # ── STEP 2: Delete old stores ──
    print("\n" + "=" * 60)
    print("STEP 2: Pulizia vecchi dati")
    print("=" * 60)

    gemini_client = genai.Client(api_key=gemini_key)
    pc = Pinecone(api_key=pinecone_key)

    delete_file_search_stores(gemini_client)
    delete_pinecone_index(pc)

    # ── STEP 3: Create new File Search Store ──
    print("\n" + "=" * 60)
    print("STEP 3: Upload PDF su nuovo File Search Store")
    print("=" * 60)

    store_name = create_file_search_store(gemini_client, upload_pdfs)

    # ── STEP 4: Extract images ──
    print("\n" + "=" * 60)
    print("STEP 4: Estrazione immagini dai PDF")
    print("=" * 60)

    all_images = []
    for pdf_path, doc_key, doc_name, page_offset in image_sources:
        imgs = extract_images(pdf_path, img_dir, doc_key, doc_name, page_offset)
        all_images.extend(imgs)

    print(f"\n  📊 Totale immagini: {len(all_images)}")

    if not all_images:
        print("  ⚠️ Nessuna immagine trovata, skippo Pinecone")
    else:
        # ── STEP 5: Embed images ──
        print("\n" + "=" * 60)
        print("STEP 5: Embedding immagini (gemini-embedding-2-preview)")
        print("=" * 60)

        embedded = embed_images(gemini_client, all_images)

        if embedded:
            # ── STEP 6: Pinecone ──
            print("\n" + "=" * 60)
            print("STEP 6: Upload su Pinecone")
            print("=" * 60)

            upload_to_pinecone(pc, embedded)

            # Save metadata
            metadata = [
                {
                    "id": img["id"],
                    "filename": img["filename"],
                    "doc_name": img["doc_name"],
                    "page": img["page"],
                    "width": img["width"],
                    "height": img["height"],
                }
                for img in embedded
            ]
            meta_path = os.path.join(img_dir, "index.json")
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)

    # Cleanup tmp
    for f in glob.glob(os.path.join(tmp_dir, "*")):
        os.remove(f)
    os.rmdir(tmp_dir)

    print(f"""
{'=' * 60}
✅ RESET E SETUP COMPLETATI!
{'=' * 60}

File Search Store: {store_name}
Immagini estratte: {len(all_images)}
Immagini embeddate: {len(embedded) if all_images else 0}

👉 Aggiorna .env.local:
   FILE_SEARCH_STORE_NAME={store_name}

{'=' * 60}
""")


if __name__ == "__main__":
    main()
