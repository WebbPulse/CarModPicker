/**
 * The extension asks the server to fetch a scraped image rather than reading
 * the bytes itself, because a service worker fetch to a retailer CDN is an
 * ordinary cross origin request that most of those CDNs refuse.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

type Listener = (
  request: Record<string, unknown>,
  sender: unknown,
  sendResponse: (response: unknown) => void,
) => boolean | undefined;

const listeners: Listener[] = [];
const syncStore: Record<string, unknown> = {
  apiUrl: "https://api.example.test/api",
};
const localStore: Record<string, unknown> = {
  authToken: "test-token",
};

/** A minimal chrome.storage area backed by a plain object. */
function area(store: Record<string, unknown>) {
  return {
    get: async (keys: string[] | string) => {
      const wanted = Array.isArray(keys) ? keys : [keys];
      const out: Record<string, unknown> = {};
      for (const k of wanted) if (k in store) out[k] = store[k];
      return out;
    },
    set: async (items: Record<string, unknown>) => {
      Object.assign(store, items);
    },
    remove: async (keys: string[] | string) => {
      for (const k of Array.isArray(keys) ? keys : [keys]) delete store[k];
    },
  };
}

/** Install the chrome API surface background.ts touches at import time. */
function installChromeMock(): void {
  (globalThis as Record<string, unknown>)["chrome"] = {
    runtime: {
      onMessage: { addListener: (fn: Listener) => listeners.push(fn) },
      onMessageExternal: { addListener: () => undefined },
      onInstalled: { addListener: () => undefined },
      id: "test-extension-id",
      getURL: (p: string) => `chrome-extension://test-extension-id/${p}`,
      lastError: undefined,
    },
    storage: {
      sync: area(syncStore),
      local: area(localStore),
    },
    tabs: {
      create: async () => ({ id: 1 }),
      remove: async () => undefined,
      onRemoved: { addListener: () => undefined },
    },
    action: { setBadgeText: async () => undefined },
  };
}

/** Send one message through the worker's listener and await its response. */
function send(request: Record<string, unknown>): Promise<any> {
  return new Promise((resolve) => {
    for (const fn of listeners) fn(request, {}, resolve);
  });
}

describe("uploadImage", () => {
  beforeEach(async () => {
    listeners.length = 0;
    vi.resetModules();
    installChromeMock();
    await import("../background");
  });

  it("asks the server to fetch the image instead of reading the bytes", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    globalThis.fetch = vi.fn(async (url: any, init?: any) => {
      calls.push({ url: String(url), init });
      if (String(url).includes("/images/by-source-url")) {
        return new Response(JSON.stringify({ detail: "not cached" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ file_key: "part/abc/img.jpg" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const res = await send({
      action: "uploadImage",
      imageUrl: "https://cdn.retailer.test/a.jpg?width=400",
      partId: "11111111-1111-1111-1111-111111111111",
    });

    expect(res).toEqual({ success: true, data: { fileKey: "part/abc/img.jpg" } });

    const fetchFromUrl = calls.find((c) => c.url.includes("/images/fetch-from-url"));
    expect(fetchFromUrl).toBeDefined();
    expect(fetchFromUrl!.init?.method).toBe("POST");

    const body = JSON.parse(String(fetchFromUrl!.init?.body));
    expect(body.entity_type).toBe("part");
    expect(body.entity_id).toBe("11111111-1111-1111-1111-111111111111");
    expect(body.source_url).toBe("https://cdn.retailer.test/a.jpg");

    const retailerHit = calls.find(
      (c) => new URL(c.url).host === "cdn.retailer.test",
    );
    expect(retailerHit).toBeUndefined();
  });

  it("returns the cached file key without asking the server to fetch", async () => {
    const calls: string[] = [];
    globalThis.fetch = vi.fn(async (url: any) => {
      calls.push(String(url));
      if (String(url).includes("/images/by-source-url")) {
        return new Response(JSON.stringify({ file_key: "part/cached/img.jpg" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error("unexpected request");
    }) as typeof fetch;

    const res = await send({
      action: "uploadImage",
      imageUrl: "https://cdn.retailer.test/b.jpg",
    });

    expect(res).toEqual({ success: true, data: { fileKey: "part/cached/img.jpg" } });
    expect(calls.some((u) => u.includes("/images/fetch-from-url"))).toBe(false);
  });

  it("surfaces a server side rejection as a failed response", async () => {
    globalThis.fetch = vi.fn(async (url: any) => {
      if (String(url).includes("/images/by-source-url")) {
        return new Response(JSON.stringify({ detail: "not cached" }), { status: 404 });
      }
      return new Response(
        JSON.stringify({ message: "Image URL resolves to a disallowed address" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }) as typeof fetch;

    const res = await send({
      action: "uploadImage",
      imageUrl: "https://internal.retailer.test/c.jpg",
    });

    expect(res.success).toBe(false);
  });

  it("omits entity_id when no part id is given", async () => {
    let body: any = null;
    globalThis.fetch = vi.fn(async (url: any, init?: any) => {
      if (String(url).includes("/images/by-source-url")) {
        return new Response(JSON.stringify({ detail: "not cached" }), { status: 404 });
      }
      body = JSON.parse(String(init?.body));
      return new Response(JSON.stringify({ file_key: "part/x/img.jpg" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    await send({ action: "uploadImage", imageUrl: "https://cdn.retailer.test/d.jpg" });

    expect(body).not.toBeNull();
    expect("entity_id" in body).toBe(false);
  });
});
