import { NextRequest, NextResponse } from "next/server";
import {
  getClient,
  getModel,
  getFileSearchStoreName,
  SYSTEM_INSTRUCTION,
  type ChatMessage,
  type ImageResult,
} from "@/lib/gemini";
import { searchImages } from "@/lib/image-search";

export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    const { messages } = (await request.json()) as { messages: ChatMessage[] };

    if (!messages || messages.length === 0) {
      return NextResponse.json(
        { error: "No messages provided" },
        { status: 400 }
      );
    }

    const client = getClient();
    const model = getModel();
    const storeName = getFileSearchStoreName();

    // Get the latest user message for image search
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
    const userQuery = lastUserMessage?.text || "";

    // Run text RAG and image search in parallel
    const contents = messages.map((msg) => ({
      role: msg.role === "model" ? "model" : "user",
      parts: [{ text: msg.text }],
    }));

    const [response, images] = await Promise.all([
      // Text RAG via Gemini File Search
      client.models.generateContent({
        model,
        contents,
        config: {
          systemInstruction: SYSTEM_INSTRUCTION,
          tools: [
            {
              fileSearch: {
                fileSearchStoreNames: [storeName],
              },
            },
          ],
          temperature: 0.3,
        },
      }),
      // Image search via Pinecone (multimodal embeddings)
      searchImages(userQuery).catch((err) => {
        console.warn("Image search failed (non-critical):", err);
        return [] as ImageResult[];
      }),
    ]);

    // Extract text response
    const text =
      response.text || "Mi dispiace, non sono riuscito a generare una risposta.";

    // Extract citations from grounding metadata
    const citations: Array<{ content: string; source: string }> = [];
    const groundingMetadata = response.candidates?.[0]?.groundingMetadata;

    if (groundingMetadata?.groundingChunks) {
      for (const chunk of groundingMetadata.groundingChunks) {
        const gc = chunk as any;
        if (gc.retrievedContext || gc.chunk) {
          citations.push({
            content:
              gc.chunk?.content || gc.retrievedContext?.text || "",
            source:
              gc.retrievedContext?.uri ||
              gc.fileSearchStore?.name ||
              "Manuale Panasonic",
          });
        }
      }
    }

    return NextResponse.json({ text, citations, images });
  } catch (error: any) {
    console.error("Chat API error:", error);

    if (error.message?.includes("FILE_SEARCH_STORE_NAME")) {
      return NextResponse.json(
        {
          error:
            "File Search Store non configurato. Esegui prima lo script di setup: python scripts/setup.py",
        },
        { status: 503 }
      );
    }

    return NextResponse.json(
      { error: error.message || "Errore interno del server" },
      { status: 500 }
    );
  }
}
