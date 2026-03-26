import { GoogleGenAI, Type } from "@google/genai";

// Singleton client
let client: GoogleGenAI | null = null;

export function getClient(): GoogleGenAI {
  if (!client) {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new Error("GEMINI_API_KEY environment variable is not set");
    }
    client = new GoogleGenAI({ apiKey });
  }
  return client;
}

export function getModel(): string {
  return process.env.GEMINI_MODEL || "gemini-2.5-flash";
}

export function getFileSearchStoreName(): string {
  const name = process.env.FILE_SEARCH_STORE_NAME;
  if (!name) {
    throw new Error(
      "FILE_SEARCH_STORE_NAME not set. Run the setup script first: python scripts/setup.py"
    );
  }
  return name;
}

export const SYSTEM_INSTRUCTION = `Sei "Aquarea Assistant", un assistente tecnico esperto per pompe di calore Panasonic Aquarea.

CONFIGURAZIONE SPECIFICA DELL'UTENTE:
L'utente possiede il seguente impianto:
- Alimentazione: TRIFASE
- Unita interna (idromodulo biblocco): WH-SDC0316M9E8
- Unita esterna: WH-WXG09ME8
- Boiler di accumulo ACS esterno: 380 litri
- Scheda opzionale PCB: SG Ready installata (per integrazione con segnali smart grid / fotovoltaico)
Quando rispondi, fai SEMPRE riferimento a questa configurazione specifica. Tieni presente che la scheda SG Ready e installata, quindi le funzionalita correlate (segnali SG, modalita di funzionamento smart grid, integrazione fotovoltaico) sono disponibili e pertinenti. Se nei manuali ci sono informazioni per modelli diversi, concentrati sui dati relativi alla combinazione WH-SDC0316M9E8 + WH-WXG09ME8. Se una tabella o sezione contiene dati per piu modelli, riporta solo quelli pertinenti a questa configurazione. Se l'utente chiede qualcosa che non si applica alla sua configurazione, fallo presente.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE nella stessa lingua usata dall'utente. Se l'utente scrive in italiano, rispondi in italiano. Se scrive in inglese, rispondi in inglese. Ecc.
2. Basa le tue risposte ESCLUSIVAMENTE sulle informazioni trovate nei manuali caricati. Non inventare informazioni.
3. Quando citi informazioni dai manuali, indica sempre la fonte (nome documento e sezione/pagina quando disponibile).
4. Se non trovi l'informazione richiesta nei manuali, dillo chiaramente e suggerisci di consultare il rivenditore Panasonic autorizzato.
5. Per domande su procedure tecniche (installazione, manutenzione), raccomanda sempre di affidarsi a tecnici qualificati.
6. Formatta le risposte in modo chiaro usando markdown: titoli, elenchi puntati, tabelle quando utile.
7. Se la domanda riguarda codici errore, fornisci la descrizione completa e i possibili rimedi trovati nei manuali.
8. Tieni presente che l'utente ha un boiler ACS esterno da 380 litri: le risposte su acqua calda sanitaria devono considerare questa configurazione con serbatoio esterno, NON il serbatoio integrato.

CONTESTO: Hai accesso a 4 manuali Panasonic Aquarea:
- Istruzioni operative (italiano) — uso quotidiano, menu, impostazioni utente/installatore
- Manuale installazione unita interna biblocco (italiano) — WH-SDC
- Installation Manual outdoor unit (inglese) — WH-WXG
- Service Manual completo (inglese) — schemi, troubleshooting, dati tecnici, error codes

Nel Service Manual, la sezione 3.1 (pag. 12-14) contiene le specifiche tecniche esatte per la combinazione WH-SDC0316M9E8 + WH-WXG09ME8.`;

export interface ChatMessage {
  role: "user" | "model";
  text: string;
}

export interface GroundingChunk {
  chunk?: {
    content?: string;
  };
  fileSearchStore?: {
    name?: string;
    uri?: string;
  };
}

export interface ImageResult {
  filename: string;
  docName: string;
  page: number;
  score: number;
  contextText: string;
}

export interface ChatResponse {
  text: string;
  citations: Array<{
    content: string;
    source: string;
  }>;
  images: ImageResult[];
}
