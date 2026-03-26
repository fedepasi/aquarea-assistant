# 🌡️ Aquarea Assistant

Chatbot interattivo per consultare i manuali della pompa di calore **Panasonic Aquarea** (serie WH-WXG / WH-SDC / WH-ADC).

Usa **Gemini File Search** (RAG gestito da Google) per cercare informazioni nei PDF dei manuali e rispondere nella lingua dell'utente.

## Quick Start

### 1. Installa le dipendenze

```bash
cd aquarea-assistant
npm install
```

### 2. Configura la API key

Crea/modifica il file `.env.local`:

```env
GEMINI_API_KEY=la-tua-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Carica i manuali PDF su Gemini

```bash
pip install google-genai
export GEMINI_API_KEY="la-tua-gemini-api-key"
python scripts/setup.py --pdf-dir /path/alla/cartella/pdf
```

Lo script stamperà il `FILE_SEARCH_STORE_NAME`. Aggiungilo a `.env.local`:

```env
FILE_SEARCH_STORE_NAME=fileSearchStores/xxxxx
```

### 4. Avvia l'app

```bash
npm run dev
```

Apri http://localhost:3000

## Deploy su Vercel

1. Pusha il repo su GitHub
2. Importa il progetto su [Vercel](https://vercel.com)
3. Aggiungi le environment variables:
   - `GEMINI_API_KEY`
   - `FILE_SEARCH_STORE_NAME`
   - `GEMINI_MODEL`
4. Deploy!

## Architettura

```
PDF Manuali → [Gemini File Search Store] → indicizzazione automatica
                                                    ↓
Utente → [Next.js React UI] → [API Route] → [Gemini + File Search]
                                                    ↓
                                        Risposta + citazioni
```

## Stack

- **Next.js 15** (App Router) — framework React
- **@google/genai** — SDK Google Gemini
- **Gemini 2.5 Flash** — modello generativo
- **Gemini File Search** — RAG gestito (chunking, embedding, retrieval automatici)
- **Tailwind CSS 4** — styling
- **Vercel** — hosting

## Manuali inclusi

| Documento | Lingua | Contenuto |
|-----------|--------|-----------|
| Istruzioni Operative | IT | Uso quotidiano, menu, impostazioni |
| Manuale Installazione Interna | IT | Installazione biblocco WH-SDC |
| Installation Manual Outdoor | EN | Installazione unità esterna WH-WXG |
| Service Manual | EN | Schemi, troubleshooting, error codes, dati tecnici |
