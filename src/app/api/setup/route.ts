import { NextRequest, NextResponse } from "next/server";
import { getClient } from "@/lib/gemini";

export const maxDuration = 300;

export async function POST(request: NextRequest) {
  try {
    const { action, storeName, filePaths } = await request.json();

    const client = getClient();

    if (action === "create_store") {
      // Create a new File Search Store
      const store = await client.fileSearchStores.create({
        config: {
          displayName: "Aquarea Panasonic Manuals",
        },
      });

      return NextResponse.json({
        success: true,
        storeName: store.name,
        message: `Store creato: ${store.name}. Aggiungi questo valore a FILE_SEARCH_STORE_NAME nel file .env.local`,
      });
    }

    if (action === "list_stores") {
      const stores = [];
      const pager = await client.fileSearchStores.list({ config: { pageSize: 20 } });

      for await (const store of pager) {
        stores.push({
          name: store.name,
          displayName: store.displayName,
          createTime: store.createTime,
        });
      }

      return NextResponse.json({ stores });
    }

    if (action === "store_status") {
      if (!storeName) {
        return NextResponse.json(
          { error: "storeName required" },
          { status: 400 }
        );
      }

      const files: any[] = [];
      const pager = await (client.fileSearchStores as any).listFiles(storeName, {
        config: { pageSize: 20 },
      });

      for await (const file of pager) {
        files.push({
          name: file.name,
          displayName: file.displayName,
          state: file.state,
          sizeBytes: file.sizeBytes,
        });
      }

      return NextResponse.json({ storeName, files });
    }

    return NextResponse.json(
      { error: "Unknown action. Use: create_store, list_stores, store_status" },
      { status: 400 }
    );
  } catch (error: any) {
    console.error("Setup API error:", error);
    return NextResponse.json(
      { error: error.message || "Setup error" },
      { status: 500 }
    );
  }
}
