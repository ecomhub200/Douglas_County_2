---
name: cloudflare-r2
description: "Cloudflare R2 object storage — CLI (Wrangler) commands and Workers API. Use when the user needs to manage R2 buckets, upload/download objects, configure CORS/lifecycles/domains, or access R2 from Cloudflare Workers via bindings."
---

# Cloudflare R2

> S3-compatible object storage with zero egress fees. Manage via Wrangler CLI or access from Cloudflare Workers via R2 bindings.

## CLI Tools Overview

| Tool | Best for |
|------|----------|
| **Wrangler** | Single object operations, bucket settings, no API credentials needed |
| **rclone** | Bulk operations, migrations, syncing directories |
| **AWS CLI** | Existing AWS workflows, S3 compatibility |

---

## Wrangler CLI

### Install & Auth

```bash
# Install
npm install -g wrangler

# Login (opens browser)
wrangler login
```

### Bucket Commands

```bash
# Create a bucket
wrangler r2 bucket create <BUCKET_NAME>

# List all buckets
wrangler r2 bucket list

# Get bucket info
wrangler r2 bucket info <BUCKET_NAME>

# Delete a bucket
wrangler r2 bucket delete <BUCKET_NAME>
```

### Object Commands

```bash
# Upload an object
wrangler r2 object put <BUCKET>/<KEY> --file ./myfile.txt

# Download an object
wrangler r2 object get <BUCKET>/<KEY> --file ./downloaded.txt

# Delete an object
wrangler r2 object delete <BUCKET>/<KEY>
```

### CORS Configuration

```bash
# Set CORS from a JSON file
wrangler r2 bucket cors set <BUCKET_NAME> --file cors.json

# List CORS rules
wrangler r2 bucket cors list <BUCKET_NAME>

# Delete CORS configuration
wrangler r2 bucket cors delete <BUCKET_NAME>
```

### Public Access (r2.dev URL)

```bash
# Enable public access via r2.dev
wrangler r2 bucket dev-url enable <BUCKET_NAME>

# Disable public access
wrangler r2 bucket dev-url disable <BUCKET_NAME>

# Get current dev URL status
wrangler r2 bucket dev-url get <BUCKET_NAME>
```

### Custom Domains

```bash
wrangler r2 bucket domain add <BUCKET_NAME>     # Add a custom domain
wrangler r2 bucket domain remove <BUCKET_NAME>   # Remove a custom domain
wrangler r2 bucket domain update <BUCKET_NAME>   # Update a custom domain
wrangler r2 bucket domain get <BUCKET_NAME>      # Get domain config
wrangler r2 bucket domain list <BUCKET_NAME>     # List all domains
```

### Object Lifecycles

```bash
# Add a lifecycle rule
wrangler r2 bucket lifecycle add <BUCKET_NAME>

# List lifecycle rules
wrangler r2 bucket lifecycle list <BUCKET_NAME>

# Remove a specific lifecycle rule
wrangler r2 bucket lifecycle remove <BUCKET_NAME>

# Set entire lifecycle config from JSON
wrangler r2 bucket lifecycle set <BUCKET_NAME> --file lifecycle.json
```

### Object Lock

```bash
wrangler r2 bucket lock add <BUCKET_NAME>     # Add a lock rule
wrangler r2 bucket lock remove <BUCKET_NAME>  # Remove a lock rule
wrangler r2 bucket lock list <BUCKET_NAME>    # List lock rules
wrangler r2 bucket lock set <BUCKET_NAME>     # Set lock config from JSON
```

### Event Notifications

```bash
wrangler r2 bucket notification create <BUCKET_NAME>  # Create notification rule
wrangler r2 bucket notification delete <BUCKET_NAME>  # Delete notification rule
wrangler r2 bucket notification list <BUCKET_NAME>    # List notification rules
```

### Data Catalog

```bash
wrangler r2 bucket catalog enable <BUCKET_NAME>   # Enable data catalog
wrangler r2 bucket catalog disable <BUCKET_NAME>  # Disable data catalog
wrangler r2 bucket catalog get <BUCKET_NAME>       # Get catalog status

# Compaction
wrangler r2 bucket catalog compaction enable <BUCKET_NAME>
wrangler r2 bucket catalog compaction disable <BUCKET_NAME>

# Snapshot expiration
wrangler r2 bucket catalog snapshot-expiration enable <BUCKET_NAME>
wrangler r2 bucket catalog snapshot-expiration disable <BUCKET_NAME>
```

### Sippy (Incremental Migration)

```bash
wrangler r2 bucket sippy enable <BUCKET_NAME>   # Enable Sippy migration
wrangler r2 bucket sippy disable <BUCKET_NAME>  # Disable Sippy
wrangler r2 bucket sippy get <BUCKET_NAME>       # Get Sippy status
```

---

## S3-Compatible CLI Tools

### rclone

```bash
# Install rclone (v1.59+)
# Configure: rclone config → S3 → Cloudflare R2

# Upload
rclone copy myfile.txt r2:my-bucket/

# Download
rclone copy r2:my-bucket/myfile.txt .

# Sync a directory
rclone sync ./local-dir r2:my-bucket/remote-dir

# List objects
rclone ls r2:my-bucket/
```

### AWS CLI

```bash
# Configure: aws configure
# Access Key ID: R2 Access Key
# Secret Access Key: R2 Secret Access Key
# Region: auto

ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"

# Upload
aws s3 cp myfile.txt s3://my-bucket/ --endpoint-url $ENDPOINT

# Download
aws s3 cp s3://my-bucket/myfile.txt ./ --endpoint-url $ENDPOINT

# List objects
aws s3 ls s3://my-bucket/ --endpoint-url $ENDPOINT

# Sync a directory
aws s3 sync ./local-dir s3://my-bucket/ --endpoint-url $ENDPOINT
```

---

## Workers API

Access R2 from Cloudflare Workers via bindings for server-side object storage operations.

Detailed reference: [references/workers-api.md](references/workers-api.md)

### Quick Setup

1. Create a bucket:

```bash
wrangler r2 bucket create my-bucket
```

2. Add R2 binding to `wrangler.jsonc` (or `wrangler.toml`):

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

3. Use in your Worker:

```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const key = url.pathname.slice(1);

    switch (request.method) {
      case "PUT":
        await env.MY_BUCKET.put(key, request.body);
        return new Response(`Put ${key} successfully!`);

      case "GET":
        const object = await env.MY_BUCKET.get(key);
        if (object === null) {
          return new Response("Object Not Found", { status: 404 });
        }
        const headers = new Headers();
        object.writeHttpMetadata(headers);
        headers.set("etag", object.httpEtag);
        return new Response(object.body, { headers });

      case "DELETE":
        await env.MY_BUCKET.delete(key);
        return new Response("Deleted!");

      default:
        return new Response("Method Not Allowed", { status: 405 });
    }
  },
};
```

### Bucket Methods (R2Bucket)

| Method | Signature | Description |
|--------|-----------|-------------|
| `head` | `(key: string): Promise<R2Object \| null>` | Get object metadata only |
| `get` | `(key: string, options?: R2GetOptions): Promise<R2ObjectBody \| R2Object \| null>` | Get object with body as ReadableStream |
| `put` | `(key: string, value: ReadableStream \| ArrayBuffer \| string \| null \| Blob, options?: R2PutOptions): Promise<R2Object \| null>` | Store an object |
| `delete` | `(key: string \| string[]): Promise<void>` | Delete object(s), up to 1000 keys per call |
| `list` | `(options?: R2ListOptions): Promise<R2Objects>` | List objects (up to 1000 per call, lexicographic order) |
| `createMultipartUpload` | `(key: string, options?: R2MultipartOptions): Promise<R2MultipartUpload>` | Start a multipart upload |
| `resumeMultipartUpload` | `(key: string, uploadId: string): R2MultipartUpload` | Resume an existing multipart upload |

### R2Object Properties

| Property | Type | Description |
|----------|------|-------------|
| `key` | `string` | Object key |
| `version` | `string` | Unique string for this upload |
| `size` | `number` | Size in bytes |
| `etag` | `string` | ETag of the object |
| `httpEtag` | `string` | Quoted ETag for HTTP headers |
| `uploaded` | `Date` | Upload timestamp |
| `httpMetadata` | `R2HTTPMetadata` | HTTP headers (content-type, cache-control, etc.) |
| `customMetadata` | `Record<string, string>` | User-defined metadata |
| `storageClass` | `'Standard' \| 'InfrequentAccess'` | Storage class |
| `checksums` | `R2Checksums` | MD5, SHA-1, SHA-256, SHA-384, SHA-512 |

### R2ObjectBody (extends R2Object)

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `body` | `ReadableStream` | Object value as a stream |
| `bodyUsed` | `boolean` | Whether body has been consumed |
| `arrayBuffer()` | `Promise<ArrayBuffer>` | Read as ArrayBuffer |
| `text()` | `Promise<string>` | Read as string |
| `json<T>()` | `Promise<T>` | Read as parsed JSON |
| `blob()` | `Promise<Blob>` | Read as Blob |

### R2GetOptions

```typescript
interface R2GetOptions {
  onlyIf?: R2Conditional | Headers;  // Conditional get (ETag, modified-since)
  range?: R2Range | Headers;        // Ranged read (offset, length, suffix)
  ssecKey?: ArrayBuffer | string;   // SSE-C encryption key (32 bytes)
}
```

### R2PutOptions

```typescript
interface R2PutOptions {
  onlyIf?: R2Conditional | Headers;      // Conditional put
  httpMetadata?: R2HTTPMetadata | Headers; // Content-Type, Cache-Control, etc.
  customMetadata?: Record<string, string>; // User-defined metadata
  md5?: ArrayBuffer | string;             // Integrity check (only one hash allowed)
  sha1?: ArrayBuffer | string;
  sha256?: ArrayBuffer | string;
  sha384?: ArrayBuffer | string;
  sha512?: ArrayBuffer | string;
  storageClass?: 'Standard' | 'InfrequentAccess';
  ssecKey?: ArrayBuffer | string;         // SSE-C encryption key
}
```

### R2ListOptions

```typescript
interface R2ListOptions {
  limit?: number;          // Max 1000 (default 1000)
  prefix?: string;         // Filter by key prefix
  cursor?: string;         // Pagination cursor from previous list
  delimiter?: string;      // Group keys (e.g., '/' for directory-like listing)
  include?: ('httpMetadata' | 'customMetadata')[];
}
```

### Conditional Operations (R2Conditional)

```typescript
interface R2Conditional {
  etagMatches?: string;        // If-Match
  etagDoesNotMatch?: string;   // If-None-Match
  uploadedBefore?: Date;       // If-Unmodified-Since
  uploadedAfter?: Date;        // If-Modified-Since
  secondsGranularity?: boolean; // Round dates to seconds
}
```

### Multipart Upload

```typescript
// Create
const upload = await env.MY_BUCKET.createMultipartUpload("large-file.zip");

// Upload parts (each part except last must be >= 5MB)
const part1 = await upload.uploadPart(1, chunk1);
const part2 = await upload.uploadPart(2, chunk2);

// Complete
const object = await upload.complete([part1, part2]);

// Or abort
await upload.abort();

// Resume an existing upload
const resumed = env.MY_BUCKET.resumeMultipartUpload("large-file.zip", uploadId);
```

### Local Development

```bash
# Local mode (default) — uses .wrangler/state on your machine
wrangler dev

# Remote mode — uses real R2 bucket
wrangler dev --remote
```

Or set in wrangler config:

```jsonc
{
  "r2_buckets": [
    {
      "binding": "MY_BUCKET",
      "bucket_name": "my-bucket",
      "remote": true  // Use real bucket during dev
    }
  ]
}
```

### Authorization Pattern

```typescript
const ALLOW_LIST = ["cat-pic.jpg"];

const hasValidHeader = (request: Request, env: Env) => {
  return request.headers.get("X-Custom-Auth-Key") === env.AUTH_KEY_SECRET;
};

function authorizeRequest(request: Request, env: Env, key: string) {
  switch (request.method) {
    case "PUT":
    case "DELETE":
      return hasValidHeader(request, env);
    case "GET":
      return ALLOW_LIST.includes(key);
    default:
      return false;
  }
}
```

Set the secret:

```bash
wrangler secret put AUTH_KEY_SECRET
```

### Deploy

```bash
wrangler deploy
```

Test with curl:

```bash
# Upload (use --data-binary, NOT -d)
curl https://your-worker.dev/myfile.txt -X PUT \
  --header "X-Custom-Auth-Key: YOUR_SECRET" \
  --data-binary @myfile.txt

# Download
curl https://your-worker.dev/myfile.txt

# Delete
curl https://your-worker.dev/myfile.txt -X DELETE \
  --header "X-Custom-Auth-Key: YOUR_SECRET"
```

## API Credentials (for S3-compatible tools)

1. Go to Cloudflare Dashboard > R2 > **Manage R2 API tokens**
2. Select **Create API token**
3. Choose **Object Read & Write** permission, select buckets
4. Copy **Access Key ID** and **Secret Access Key** (secret shown only once)

S3 API endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

## Specific tasks

* **Workers API detailed reference** [references/workers-api.md](references/workers-api.md)
