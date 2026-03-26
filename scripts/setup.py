#!/usr/bin/env python3
"""
Aquarea Assistant — Setup Script
================================
Questo script:
1. Crea un File Search Store su Gemini
2. Carica i 4 PDF dei manuali Panasonic Aquarea
3. Attende l'indicizzazione
4. Stampa il nome dello store da inserire in .env.local

Prerequisiti:
  pip install google-genai

Uso:
  export GEMINI_API_KEY="la-tua-api-key"
  python scripts/setup.py

  Oppure passa i PDF da una cartella specifica:
  python scripts/setup.py --pdf-dir /path/to/pdfs
"""

import os
import sys
import time
import glob
import argparse
from google import genai
from google.genai import types

def main():
    parser = argparse.ArgumentParser(description="Setup Aquarea Assistant File Search Store")
    parser.add_argument("--pdf-dir", default=None, help="Directory contenente i PDF (default: cartella padre dello script)")
    parser.add_argument("--api-key", default=None, help="Gemini API key (default: env GEMINI_API_KEY)")
    parser.add_argument("--store-name", default=None, help="Nome di uno store esistente da riutilizzare")
    args = parser.parse_args()

    # API Key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY non trovata. Impostala come variabile d'ambiente o usa --api-key")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Find PDFs
    if args.pdf_dir:
        pdf_dir = args.pdf_dir
    else:
        # Default: look in parent directory (project root, where PDFs are alongside the app)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pdf_dir = os.path.dirname(script_dir)  # Go up from scripts/ to project root
        # Also check parent of project for the mounted folder
        parent_dir = os.path.dirname(pdf_dir)

        # Try to find PDFs in multiple locations
        for search_dir in [pdf_dir, parent_dir]:
            pdfs = glob.glob(os.path.join(search_dir, "*.pdf"))
            if pdfs:
                pdf_dir = search_dir
                break

    pdfs = glob.glob(os.path.join(pdf_dir, "*.pdf"))

    if not pdfs:
        print(f"❌ Nessun PDF trovato in: {pdf_dir}")
        print("   Usa --pdf-dir per specificare la cartella dei PDF")
        sys.exit(1)

    print(f"\n📂 Trovati {len(pdfs)} PDF in: {pdf_dir}")
    for pdf in pdfs:
        size_mb = os.path.getsize(pdf) / (1024 * 1024)
        print(f"   📄 {os.path.basename(pdf)} ({size_mb:.1f} MB)")

    # Create or reuse File Search Store
    if args.store_name:
        store_name = args.store_name
        print(f"\n♻️  Riutilizzo store esistente: {store_name}")
    else:
        print("\n🏗️  Creazione File Search Store...")
        store = client.file_search_stores.create(
            config={"display_name": "Aquarea Panasonic Manuals"}
        )
        store_name = store.name
        print(f"   ✅ Store creato: {store_name}")

    # Upload PDFs
    print(f"\n📤 Upload dei PDF nello store...")
    operations = []

    # Map of PDF filenames to friendly display names
    display_names = {
        "dc5dc2c8": "Istruzioni Operative (IT)",
        "e55f1de8": "Manuale Installazione Interna (IT)",
        "7e0ff8df": "Installation Manual Outdoor (EN)",
        "e834acce": "Service Manual Completo (EN)",
    }

    for pdf_path in pdfs:
        basename = os.path.basename(pdf_path)
        # Try to find a friendly display name
        display_name = basename
        for key, friendly_name in display_names.items():
            if key in basename:
                display_name = friendly_name
                break

        print(f"   📤 Uploading: {display_name}...")
        try:
            operation = client.file_search_stores.upload_to_file_search_store(
                file=pdf_path,
                file_search_store_name=store_name,
                config={"display_name": display_name},
            )
            operations.append((display_name, operation))
            print(f"      ✅ Upload avviato")
        except Exception as e:
            print(f"      ❌ Errore: {e}")

    # Wait for indexing to complete
    print(f"\n⏳ Attendo l'indicizzazione dei documenti...")
    for display_name, operation in operations:
        while not operation.done:
            print(f"   ⏳ {display_name}: indicizzazione in corso...")
            time.sleep(10)
            operation = client.operations.get(operation)
        print(f"   ✅ {display_name}: indicizzazione completata!")

    # Verify
    print(f"\n📋 Verifica files nello store:")
    try:
        pager = client.file_search_stores.list_files(store_name, config={"page_size": 50})
        file_count = 0
        for f in pager:
            file_count += 1
            state = getattr(f, 'state', 'unknown')
            print(f"   📄 {f.display_name or f.name} — stato: {state}")
        print(f"\n   Totale: {file_count} file(s)")
    except Exception as e:
        print(f"   ⚠️ Errore nella verifica: {e}")

    # Print final instructions
    print(f"""
{'='*60}
✅ SETUP COMPLETATO!
{'='*60}

Il tuo File Search Store è pronto.

👉 Aggiungi questa riga al file .env.local:

   FILE_SEARCH_STORE_NAME={store_name}

Poi avvia l'app:
   cd aquarea-assistant
   npm run dev

{'='*60}
""")


if __name__ == "__main__":
    main()
