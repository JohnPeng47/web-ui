# Improve HTTP request body parsing
_Exported on 10/11/2025 at 15:30:16 EDT from Cursor (1.7.39)_

---

**User**

I have the following code in my own HTTP request parsing code:
def post_data_to_dict(post_data: str | None):
    """Convert post data to dictionary format.
    
    Args:
        post_data: Raw post data string
        
    Returns:
        Dictionary of post data parameters
    """
    if not post_data:
        return {}
    
    result = {}
    
    # Handle URL-encoded form data (param1=value1&param2=value2)
    if isinstance(post_data, str):
        if "&" in post_data:
            pairs = post_data.split("&")
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    result[key] = value
        # Try to parse as JSON
        elif post_data.strip().startswith("{") and post_data.strip().endswith("}"):
            try:
                result = json.loads(post_data)
            except json.JSONDecodeError:
                # Not valid JSON, return as is
                pass
    
    return result

class ResourceLocator(BaseModel):
    """How to locate a particular resource id in a template request."""
    id: str
    request_part: RequestPart
    type_name: str

# TODO: support for CSRF tokens
class AuthSession(BaseModel):
    headers: Dict[str, str]
    body: Optional[Dict[str, str]] = None

class HTTPRequestData(BaseModel):
    """Internal representation of HTTP request data"""
    method: str
    url: str
    headers: Dict[str, str]
    post_data: Optional[Dict] = None
    redirected_from_url: Optional[str] = ""
    redirected_to_url: Optional[str] = ""
    is_iframe: bool = False


But this seems very rudimentary, can you find how this repo does http request body parsing, and highlight improvements that can be made to my own code?

---

**Cursor**

I'll scan the codebase to find where HTTP request body parsing/formatting is implemented, focusing on JSON, urlencoded, and multipart handling, then extract relevant snippets to compare and suggest improvements.

I'll open the core files that implement request body decoding, content-type detection, and urlencoded parsing in this repo to extract the relevant logic and compare against your function.

I scanned the repo for where it decodes and interprets request bodies; below I’ve cited the key spots and distilled concrete improvements you can apply to your function.

### Where this repo handles HTTP request bodies

- Decoding raw bytes (gzip/deflate/br) based on Content-Encoding, then exposing a decoded buffer:
```24:41:src/model/http/http-body.ts
export class HttpBody implements MessageBody {
    constructor(
        message: InputMessage | { body: Buffer },
        headers: Headers | RawHeaders
    ) {
        this._contentEncoding = asHeaderArray(getHeaderValues(headers, 'content-encoding'));

        if (!('body' in message) || !message.body) {
            this._encoded = stringToBuffer("");
        } else if (Buffer.isBuffer(message.body)) {
            this._encoded = message.body;
        } else if ('buffer' in message.body) {
            this._encoded = message.body.buffer;
        } else {
            this._encoded = fakeBuffer(message.body.encodedLength);
            this._decoded = message.body.decoded;
        }
    }
```

```125:136:src/model/http/http-body.ts
                try {
                    const { decoded } = decodingRequired(encodedBuffer, this._contentEncoding)
                        ? await decodeBody(encodedBuffer, this._contentEncoding)
                        : { decoded: encodedBuffer };

                    runInAction(() => {
                        this._decoded = decoded;
                    });

                    return decoded;
```

- Mapping Content-Type to a normalized “viewable content type” (e.g. url-encoded, json):
```88:93:src/model/events/content-types.ts
    'application/x-www-form-urlencoded': 'url-encoded',

    'text/markdown': 'markdown',
    'text/x-markdown': 'markdown',
```

```136:139:src/model/events/content-types.ts
export function getContentType(mimeType: string | undefined): ViewableContentType | undefined {
    const baseContentType = getBaseContentType(mimeType);
    return mimeTypeToContentTypeMap[baseContentType!];
}
```

- Parsing urlencoded bodies robustly using a standard parser (handles percent-decoding, + as space, repeated keys → arrays):
```260:272:src/model/http/har.ts
function generateHarPostBody(body: string | false, mimeType: string): TextBody | ParamBody | undefined {
    if (!body) return;

    if (mimeType === 'application/x-www-form-urlencoded') {
        let parsedBody: querystring.ParsedUrlQuery | undefined;

        try {
            parsedBody = querystring.parse(body);
        } catch (e) {
            console.log('Failed to parse url encoded body', body);
        }
```

```797:810:src/model/http/har.ts
function parseHarPostData(data: HarFormat.PostData | undefined): Buffer {
    if (data?.text) {
        return stringToBuffer(data.text, 'utf8');
    } else if (data?.params) {
        return stringToBuffer(
            querystring.stringify(_(data.params)
                .groupBy(({ name }) => name)
                .mapValues((params) => params.map(p => p.value || ''))
                .valueOf()
            )
        );
    } else {
        return stringToBuffer('');
    }
}
```

- Assigning a request’s `contentType` based on headers and constructing the body wrapper:
```79:90:src/model/http/http-exchange.ts
function addRequestMetadata(request: InputRequest): HtkRequest {
    try {
        return Object.assign(request, {
            parsedUrl: request.url
                ? tryParseUrl(request.url)
                : unparseableUrl,
            source: request.tags.includes('httptoolkit:manually-sent-request')
                ? MANUALLY_SENT_SOURCE
                : parseSource(request.headers['user-agent']),
            body: new HttpBody(request, request.headers),
            contentType: getContentType(getHeaderValue(request.headers, 'content-type')) || 'text',
            cache: new ObservableCache()
        }) as HtkRequest;
    } catch (e) {
```

- JSON parsing done conditionally, with validation in some flows (example from JSON-RPC support):
```39:55:src/model/api/jsonrpc.ts
    try {
        const body = await exchange.request.body.waitForDecoding();

        if (!body?.length) throw new Error(`No JSON-RPC request body`);

        let parsedBody: any;
        let methodName: string;
        try {
            parsedBody = JSON.parse(body?.toString());
            if (parsedBody.jsonrpc !== '2.0') throw new Error(
                `JSON-RPC request body had bad 'jsonrpc' field: ${parsedBody.jsonrpc}`
            );

            methodName = parsedBody.method;
        } catch (e) {
            console.warn(e);
            throw new Error('Could not parse JSON-RPC request body');
        }
```

### Improvements to your `post_data_to_dict` function

- Content-Encoding support: decompress gzip/deflate/br before parsing.
- Content-Type aware parsing:
  - application/x-www-form-urlencoded: use a real parser (percent-decoding, + spaces, duplicate keys → lists).
  - application/json: parse JSON reliably; don’t rely on string startswith/endswith.
  - multipart/form-data: parse via a library (e.g. `python-multipart`, `werkzeug`, or `email` parser) to handle files and fields.
- Charset handling: honor `charset` from `Content-Type`; default to utf-8 with a fallback detector if needed.
- Preserve multi-values: don’t overwrite duplicates; return lists where appropriate.
- Robust errors and limits: size guards to avoid parsing huge bodies; return both raw and parsed on failure.
- Heuristics when headers are missing: optionally attempt JSON if it “looks like” JSON; otherwise leave raw.
- Keep raw alongside parsed: similar to `HttpBody`, maintain the original string/bytes and any errors.

A compact Python sketch illustrating the core fixes (urlencoded + JSON + encoding + decoding); adapt as needed:
```python
import json
import zlib
import brotli
from urllib.parse import parse_qs
from cgi import parse_header

def decode_body_bytes(body: bytes, content_encoding: str | None) -> bytes:
    if not body:
        return b""
    enc = (content_encoding or "").lower()
    if "br" in enc:
        return brotli.decompress(body)
    if "gzip" in enc:
        return zlib.decompress(body, zlib.MAX_WBITS | 16)
    if "deflate" in enc:
        try:
            return zlib.decompress(body, -zlib.MAX_WBITS)
        except zlib.error:
            return zlib.decompress(body)
    return body

def detect_charset(content_type: str | None) -> str:
    if not content_type:
        return "utf-8"
    _type, params = parse_header(content_type)
    return params.get("charset", "utf-8")

def post_data_to_dict(post_data: bytes | str | None, headers: dict[str, str] | None = None):
    if not post_data:
        return {}

    headers = headers or {}
    content_type = headers.get("Content-Type") or headers.get("content-type")
    content_encoding = headers.get("Content-Encoding") or headers.get("content-encoding")

    # Normalize to bytes
    if isinstance(post_data, str):
        post_bytes = post_data.encode(detect_charset(content_type), errors="replace")
    else:
        post_bytes = post_data

    # Decode content-encoding first
    try:
        decoded_bytes = decode_body_bytes(post_bytes, content_encoding)
    except Exception:
        decoded_bytes = post_bytes  # fall back to raw if decoding fails

    # Decode to text using charset
    charset = detect_charset(content_type)
    text = decoded_bytes.decode(charset, errors="replace")

    base_ct = (content_type or "").split(";")[0].strip().lower()

    if base_ct == "application/x-www-form-urlencoded":
        # Preserves duplicates -> lists; keep_blank_values ensures a=b&c= becomes {"a":["b"],"c":[""]}
        return {k: v if len(v) > 1 else v[0] for k, v in parse_qs(text, keep_blank_values=True).items()}

    if base_ct in ("application/json", "text/json") or text.lstrip().startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text}

    # TODO: multipart/form-data support via a multipart parser if required
    return {"_raw": text}
```

This addresses:
- Proper decoding (gzip/deflate/br).
- Correct charset decoding.
- Standards-compliant urlencoded parsing (percent-decoding, plus-as-space, duplicates).
- Safer JSON detection and parsing.
- Retaining raw data on unknown types or parse failures.

If you need multipart/form-data too, I can add a minimal `python-multipart` or `email`-based implementation next.

- I found the body decoding, content-type mapping, and urlencoded/JSON handling in `src/model/http/http-body.ts`, `src/model/events/content-types.ts`, `src/model/http/har.ts`, `src/model/http/http-exchange.ts`, and `src/model/api/jsonrpc.ts`. I then summarized the repo’s approach and provided a compact Python revision that adds encoding-aware, content-type-driven parsing, preserves multi-values, and handles compressed bodies.

```typescript
export class HttpBody implements MessageBody {
    constructor(
        message: InputMessage | { body: Buffer },
        headers: Headers | RawHeaders
    ) {
        this._contentEncoding = asHeaderArray(getHeaderValues(headers, 'content-encoding'));

        if (!('body' in message) || !message.body) {
            this._encoded = stringToBuffer("");
        } else if (Buffer.isBuffer(message.body)) {
            this._encoded = message.body;
        } else if ('buffer' in message.body) {
            this._encoded = message.body.buffer;
        } else {
            this._encoded = fakeBuffer(message.body.encodedLength);
            this._decoded = message.body.decoded;
        }
    }
```

```typescript
                try {
                    const { decoded } = decodingRequired(encodedBuffer, this._contentEncoding)
                        ? await decodeBody(encodedBuffer, this._contentEncoding)
                        : { decoded: encodedBuffer };

                    runInAction(() => {
                        this._decoded = decoded;
                    });

                    return decoded;
```

```typescript
    'application/x-www-form-urlencoded': 'url-encoded',

    'text/markdown': 'markdown',
    'text/x-markdown': 'markdown',
```

```typescript
export function getContentType(mimeType: string | undefined): ViewableContentType | undefined {
    const baseContentType = getBaseContentType(mimeType);
    return mimeTypeToContentTypeMap[baseContentType!];
}
```

```typescript
function generateHarPostBody(body: string | false, mimeType: string): TextBody | ParamBody | undefined {
    if (!body) return;

    if (mimeType === 'application/x-www-form-urlencoded') {
        let parsedBody: querystring.ParsedUrlQuery | undefined;

        try {
            parsedBody = querystring.parse(body);
        } catch (e) {
            console.log('Failed to parse url encoded body', body);
        }
```

```typescript
function parseHarPostData(data: HarFormat.PostData | undefined): Buffer {
    if (data?.text) {
        return stringToBuffer(data.text, 'utf8');
    } else if (data?.params) {
        return stringToBuffer(
            querystring.stringify(_(data.params)
                .groupBy(({ name }) => name)
                .mapValues((params) => params.map(p => p.value || ''))
                .valueOf()
            )
        );
    } else {
        return stringToBuffer('');
    }
}
```

```typescript
function addRequestMetadata(request: InputRequest): HtkRequest {
    try {
        return Object.assign(request, {
            parsedUrl: request.url
                ? tryParseUrl(request.url)
                : unparseableUrl,
            source: request.tags.includes('httptoolkit:manually-sent-request')
                ? MANUALLY_SENT_SOURCE
                : parseSource(request.headers['user-agent']),
            body: new HttpBody(request, request.headers),
            contentType: getContentType(getHeaderValue(request.headers, 'content-type')) || 'text',
            cache: new ObservableCache()
        }) as HtkRequest;
    } catch (e) {
```

```typescript
    try {
        const body = await exchange.request.body.waitForDecoding();

        if (!body?.length) throw new Error(`No JSON-RPC request body`);

        let parsedBody: any;
        let methodName: string;
        try {
            parsedBody = JSON.parse(body?.toString());
            if (parsedBody.jsonrpc !== '2.0') throw new Error(
                `JSON-RPC request body had bad 'jsonrpc' field: ${parsedBody.jsonrpc}`
            );

            methodName = parsedBody.method;
        } catch (e) {
            console.warn(e);
            throw new Error('Could not parse JSON-RPC request body');
        }
```

```python
import json
import zlib
import brotli
from urllib.parse import parse_qs
from cgi import parse_header

def decode_body_bytes(body: bytes, content_encoding: str | None) -> bytes:
    if not body:
        return b""
    enc = (content_encoding or "").lower()
    if "br" in enc:
        return brotli.decompress(body)
    if "gzip" in enc:
        return zlib.decompress(body, zlib.MAX_WBITS | 16)
    if "deflate" in enc:
        try:
            return zlib.decompress(body, -zlib.MAX_WBITS)
        except zlib.error:
            return zlib.decompress(body)
    return body

def detect_charset(content_type: str | None) -> str:
    if not content_type:
        return "utf-8"
    _type, params = parse_header(content_type)
    return params.get("charset", "utf-8")

def post_data_to_dict(post_data: bytes | str | None, headers: dict[str, str] | None = None):
    if not post_data:
        return {}

    headers = headers or {}
    content_type = headers.get("Content-Type") or headers.get("content-type")
    content_encoding = headers.get("Content-Encoding") or headers.get("content-encoding")

    # Normalize to bytes
    if isinstance(post_data, str):
        post_bytes = post_data.encode(detect_charset(content_type), errors="replace")
    else:
        post_bytes = post_data

    # Decode content-encoding first
    try:
        decoded_bytes = decode_body_bytes(post_bytes, content_encoding)
    except Exception:
        decoded_bytes = post_bytes  # fall back to raw if decoding fails

    # Decode to text using charset
    charset = detect_charset(content_type)
    text = decoded_bytes.decode(charset, errors="replace")

    base_ct = (content_type or "").split(";")[0].strip().lower()

    if base_ct == "application/x-www-form-urlencoded":
        # Preserves duplicates -> lists; keep_blank_values ensures a=b&c= becomes {"a":["b"],"c":[""]}
        return {k: v if len(v) > 1 else v[0] for k, v in parse_qs(text, keep_blank_values=True).items()}

    if base_ct in ("application/json", "text/json") or text.lstrip().startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text}

    # TODO: multipart/form-data support via a multipart parser if required
    return {"_raw": text}
```

