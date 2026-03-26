import { getClient } from "./gemini";
import type { ImageResult } from "./gemini";

const EMBEDDING_MODEL = "gemini-embedding-2-preview";
const EMBEDDING_DIM = 768;
const TOP_K = 3;
const MIN_SCORE = 0.45; // Minimum cosine similarity to include (45%) — multimodal cross-modal scores are inherently lower than text-text

/**
 * Embed a text query using gemini-embedding-2-preview (multimodal model).
 * Since text and images share the same embedding space, a text query
 * can find semantically similar images.
 */
async function embedQuery(query: string): Promise<number[]> {
  const client = getClient();

  const result = await client.models.embedContent({
    model: EMBEDDING_MODEL,
    contents: query,
    config: {
      outputDimensionality: EMBEDDING_DIM,
      taskType: "QUESTION_ANSWERING",
    },
  });

  if (!result.embeddings || result.embeddings.length === 0) {
    throw new Error("Failed to generate query embedding");
  }

  return result.embeddings[0].values as number[];
}

/**
 * Query Pinecone for similar images using the REST API.
 * We use fetch directly to avoid adding the Pinecone JS SDK as a dependency.
 */
async function queryPinecone(
  embedding: number[],
  topK: number = TOP_K
): Promise<ImageResult[]> {
  const apiKey = process.env.PINECONE_API_KEY;
  const indexName = process.env.PINECONE_INDEX || "aquarea-images";

  if (!apiKey) {
    console.warn("PINECONE_API_KEY not set, skipping image search");
    return [];
  }

  // First, get the index host from Pinecone
  const describeResponse = await fetch(
    `https://api.pinecone.io/indexes/${indexName}`,
    {
      headers: {
        "Api-Key": apiKey,
        "X-Pinecone-API-Version": "2025-01",
      },
    }
  );

  if (!describeResponse.ok) {
    console.warn(`Pinecone index '${indexName}' not found or error: ${describeResponse.status}`);
    return [];
  }

  const indexInfo = await describeResponse.json();
  const host = indexInfo.host;

  if (!host) {
    console.warn("Could not determine Pinecone index host");
    return [];
  }

  // Query the index
  const queryResponse = await fetch(`https://${host}/query`, {
    method: "POST",
    headers: {
      "Api-Key": apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      vector: embedding,
      topK,
      includeMetadata: true,
    }),
  });

  if (!queryResponse.ok) {
    console.warn(`Pinecone query failed: ${queryResponse.status}`);
    return [];
  }

  const data = await queryResponse.json();

  if (!data.matches) {
    return [];
  }

  return data.matches
    .filter((match: any) => match.score >= MIN_SCORE)
    .map((match: any) => ({
      filename: match.metadata?.filename || "",
      docName: match.metadata?.doc_name || "Unknown",
      page: match.metadata?.page || 0,
      score: match.score,
      contextText: match.metadata?.context_text || "",
    }));
}

/**
 * Search for relevant images given a user query.
 * Uses gemini-embedding-2-preview to embed the query (text),
 * then searches Pinecone for similar images (cross-modal search).
 */
export async function searchImages(query: string): Promise<ImageResult[]> {
  try {
    const embedding = await embedQuery(query);
    const results = await queryPinecone(embedding);
    return results;
  } catch (error) {
    console.error("Image search error:", error);
    return [];
  }
}
