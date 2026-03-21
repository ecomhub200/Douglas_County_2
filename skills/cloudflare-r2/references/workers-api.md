# Cloudflare R2 Workers API Reference

Complete reference for accessing R2 from Cloudflare Workers via bindings.

## Binding Configuration

Add to `wrangler.jsonc` (or `wrangler.toml`):

```jsonc
{
  "r2_buckets": [
    {
      "binding": "MY_BUCKET",
      "bucket_name": "my-bucket"
    }
  ]
}
```

The binding is available as `env.MY_BUCKET` in your Worker code.

## Full CRUD Example (TypeScript)

```typescript
import { WorkerEntrypoint } from "cloudflare:workers";

interface Env {
  R2: R2Bucket;
}

export default class extends WorkerEntrypoint<Env> {
  async fetch(request: Request) {
    const url = new URL(request.url);
    const key = url.pathname.slice(1);

    switch (request.method) {
      case "PUT": {
        await this.env.R2.put(key, request.body, {
          onlyIf: request.headers,
          httpMetadata: request.headers,
        });
        return new Response(`Put ${key} successfully!`);
      }
      case "GET": {
        const object = await this.env.R2.get(key, {
          onlyIf: request.headers,
          range: request.headers,
        });

        if (object === null) {
          return new Response("Object Not Found", { status: 404 });
        }

        const headers = new Headers();
        object.writeHttpMetadata(headers);
        headers.set("etag", object.httpEtag);

        // When no body is present, preconditions have failed
        return new Response("body" in object ? object.body : undefined, {
          status: "body" in object ? 200 : 412,
          headers,
        });
      }
      case "DELETE": {
        await this.env.R2.delete(key);
        return new Response("Deleted!");
      }
      default:
        return new Response("Method Not Allowed", {
          status: 405,
          headers: { Allow: "PUT, GET, DELETE" },
        });
    }
  }
}
```

## Full CRUD Example (JavaScript)

```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = url.pathname.slice(1);

    switch (request.method) {
      case "PUT": {
        await env.MY_BUCKET.put(key, request.body, {
          onlyIf: request.headers,
          httpMetadata: request.headers,
        });
        return new Response(`Put ${key} successfully!`);
      }
      case "GET": {
        const object = await env.MY_BUCKET.get(key, {
          onlyIf: request.headers,
          range: request.headers,
        });

        if (object === null) {
          return new Response("Object Not Found", { status: 404 });
        }

        const headers = new Headers();
        object.writeHttpMetadata(headers);
        headers.set("etag", object.httpEtag);

        return new Response("body" in object ? object.body : undefined, {
          status: "body" in object ? 200 : 412,
          headers,
        });
      }
      case "DELETE": {
        await env.MY_BUCKET.delete(key);
        return new Response("Deleted!");
      }
      default:
        return new Response("Method Not Allowed", {
          status: 405,
          headers: { Allow: "PUT, GET, DELETE" },
        });
    }
  },
};
```

## Bucket Method Details

### head(key)

Retrieves only object metadata (no body).

```typescript
const obj = await env.MY_BUCKET.head("my-key");
if (obj) {
  console.log(obj.key, obj.size, obj.etag, obj.uploaded);
}
```

### get(key, options?)

Retrieves object with body as ReadableStream.

```typescript
// Simple get
const obj = await env.MY_BUCKET.get("my-key");
if (obj) {
  const text = await obj.text();      // Read as string
  const json = await obj.json();      // Read as JSON
  const buf = await obj.arrayBuffer(); // Read as ArrayBuffer
  const blob = await obj.blob();      // Read as Blob
  // Or stream: obj.body (ReadableStream)
}

// Conditional get (returns R2Object without body if precondition fails)
const obj = await env.MY_BUCKET.get("my-key", {
  onlyIf: {
    etagMatches: '"abc123"',
  },
});

// Ranged read
const obj = await env.MY_BUCKET.get("my-key", {
  range: { offset: 0, length: 1024 },  // First 1KB
});

// Suffix read
const obj = await env.MY_BUCKET.get("my-key", {
  range: { suffix: 512 },  // Last 512 bytes
});

// Using HTTP headers for conditional + range
const obj = await env.MY_BUCKET.get("my-key", {
  onlyIf: request.headers,
  range: request.headers,
});
```

### put(key, value, options?)

Store an object. Writes are strongly consistent.

```typescript
// Simple put
await env.MY_BUCKET.put("my-key", "Hello World");

// Put with metadata
await env.MY_BUCKET.put("image.png", imageBuffer, {
  httpMetadata: {
    contentType: "image/png",
    cacheControl: "public, max-age=86400",
  },
  customMetadata: {
    uploadedBy: "user-123",
    category: "photos",
  },
});

// Put from request body (streaming)
await env.MY_BUCKET.put("upload.bin", request.body);

// Conditional put (returns null if precondition fails)
const result = await env.MY_BUCKET.put("my-key", data, {
  onlyIf: {
    etagDoesNotMatch: '"existing-etag"',
  },
});

// Put with integrity check
await env.MY_BUCKET.put("my-key", data, {
  sha256: expectedHash,
});

// Put with storage class
await env.MY_BUCKET.put("archive.zip", data, {
  storageClass: "InfrequentAccess",
});
```

Accepted value types: `ReadableStream`, `ArrayBuffer`, `ArrayBufferView`, `string`, `null`, `Blob`.

### delete(key)

Delete objects. Strongly consistent.

```typescript
// Single delete
await env.MY_BUCKET.delete("my-key");

// Batch delete (up to 1000 keys)
await env.MY_BUCKET.delete(["key1", "key2", "key3"]);
```

### list(options?)

List objects. Returns up to 1000 entries, lexicographically ordered.

```typescript
// Simple list
const listed = await env.MY_BUCKET.list();
for (const obj of listed.objects) {
  console.log(obj.key, obj.size);
}

// With prefix filter
const listed = await env.MY_BUCKET.list({
  prefix: "images/",
  limit: 100,
});

// Directory-like listing with delimiter
const listed = await env.MY_BUCKET.list({
  prefix: "data/",
  delimiter: "/",
});
// listed.objects = files directly in data/
// listed.delimitedPrefixes = ["data/subdir1/", "data/subdir2/"]

// Paginated listing
let cursor: string | undefined;
do {
  const listed = await env.MY_BUCKET.list({ cursor });
  for (const obj of listed.objects) {
    console.log(obj.key);
  }
  cursor = listed.truncated ? listed.cursor : undefined;
} while (cursor);

// Include metadata in listing
const listed = await env.MY_BUCKET.list({
  include: ["httpMetadata", "customMetadata"],
});
```

## Multipart Upload

For large files (parts must be >= 5MB except the last part).

```typescript
// Create multipart upload
const mpu = await env.MY_BUCKET.createMultipartUpload("large-file.zip", {
  httpMetadata: { contentType: "application/zip" },
  customMetadata: { source: "bulk-upload" },
});

// Upload parts
const part1 = await mpu.uploadPart(1, chunk1);
const part2 = await mpu.uploadPart(2, chunk2);
const part3 = await mpu.uploadPart(3, chunk3);

// Complete (pass all uploaded parts)
const object = await mpu.complete([part1, part2, part3]);

// Or abort if needed
await mpu.abort();
```

### Resume a Multipart Upload

```typescript
// Resume from another request/worker invocation
const mpu = env.MY_BUCKET.resumeMultipartUpload("large-file.zip", uploadId);
const part = await mpu.uploadPart(nextPartNumber, chunkData);
```

### Multipart Worker Example

```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const key = url.pathname.slice(1);
    const action = url.searchParams.get("action");

    switch (action) {
      case "mpu-create": {
        const upload = await env.MY_BUCKET.createMultipartUpload(key);
        return Response.json({
          key: upload.key,
          uploadId: upload.uploadId,
        });
      }
      case "mpu-upload": {
        const uploadId = url.searchParams.get("uploadId")!;
        const partNumber = parseInt(url.searchParams.get("partNumber")!);
        const upload = env.MY_BUCKET.resumeMultipartUpload(key, uploadId);
        const part = await upload.uploadPart(partNumber, request.body!);
        return Response.json({
          partNumber: part.partNumber,
          etag: part.etag,
        });
      }
      case "mpu-complete": {
        const uploadId = url.searchParams.get("uploadId")!;
        const upload = env.MY_BUCKET.resumeMultipartUpload(key, uploadId);
        const { parts } = await request.json<{ parts: R2UploadedPart[] }>();
        const object = await upload.complete(parts);
        return new Response(null, {
          headers: { etag: object.httpEtag },
        });
      }
      default:
        return new Response("Unknown action", { status: 400 });
    }
  },
};
```

## Conditional Operations

Use `R2Conditional` for optimistic concurrency and cache validation:

```typescript
interface R2Conditional {
  etagMatches?: string;        // Succeed if ETag matches (If-Match)
  etagDoesNotMatch?: string;   // Succeed if ETag doesn't match (If-None-Match)
  uploadedBefore?: Date;       // Succeed if uploaded before (If-Unmodified-Since)
  uploadedAfter?: Date;        // Succeed if uploaded after (If-Modified-Since)
  secondsGranularity?: boolean; // Round timestamp comparisons to seconds
}
```

For `get()`: If condition fails, body is not returned (lower latency).
For `put()`: If condition fails, returns `null` and object is not stored.

You can also pass standard HTTP `Headers` objects directly.

## HTTP Metadata

```typescript
interface R2HTTPMetadata {
  contentType?: string;
  contentLanguage?: string;
  contentDisposition?: string;
  contentEncoding?: string;
  cacheControl?: string;
  cacheExpiry?: Date;
}
```

Use `object.writeHttpMetadata(headers)` to apply stored metadata to a `Headers` object.

## Checksums

Returned on `R2Object.checksums`:

```typescript
interface R2Checksums {
  md5?: ArrayBuffer;     // Included by default for non-multipart objects
  sha1?: ArrayBuffer;
  sha256?: ArrayBuffer;
  sha384?: ArrayBuffer;
  sha512?: ArrayBuffer;
}
```

## Storage Classes

- `Standard` — Default, optimized for frequent access
- `InfrequentAccess` — Lower cost for rarely accessed data

Set via `R2PutOptions.storageClass` or lifecycle rules.

## Local Development

By default, `wrangler dev` uses local storage (`.wrangler/state` folder). Objects don't affect production.

```bash
# Local (default)
wrangler dev

# Remote (uses real R2 bucket)
wrangler dev --remote
```

Or configure in binding:

```jsonc
{
  "r2_buckets": [
    {
      "binding": "MY_BUCKET",
      "bucket_name": "my-bucket",
      "remote": true
    }
  ]
}
```

## Important Notes

- R2 writes are **strongly consistent** — once a `put()` resolves, all subsequent reads see the new value globally
- R2 deletes are **strongly consistent** — once `delete()` resolves, the key is gone globally
- `delete()` accepts up to **1000 keys** per call
- `list()` returns up to **1000 entries** per call; use `cursor` for pagination
- Multipart upload parts must be **>= 5MB** (except the last part)
- Uncompleted multipart uploads are **auto-aborted after 7 days**
- Use `httpEtag` (quoted) in response headers, not `etag` (unquoted)
- When uploading via curl, use `--data-binary` not `-d` to avoid truncation
