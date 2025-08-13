from openai import OpenAI
client = OpenAI()

CRITERIA = """
Below is a consolidated **“master list” of endpoint-selection / scoring filters** discussed so far.
I have grouped them into six logical buckets, noted synonyms, and (where relevant) shown a *typical data source or heuristic* your pipeline might use. Use or drop weightings as suits your ranking model.

---

## A. Surface & Reachability

| #   | Filter (a.k.a)                     | What you measure                                                         | Typical signal / metric                                  |
| --- | ---------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------- |
| A-1 | **HTTP status profile**            | Does the base URI return 200, 301/302, 4xx/5xx?                          | First-hit `GET /` and a few common probe paths           |
| A-2 | **Redirect depth & patterns**      | Presence of single / multi-hop redirects, SAML hops, captive portal flow | `Location:` chain length, external vs internal hostnames |
| A-3 | **Number of reachable endpoints**  | Breadth of enumerated URIs before auth                                   | Count of unique 2xx responses from crawler               |
| A-4 | **Pre-auth vs post-auth exposure** | Is the interesting endpoint unauthenticated?                             | Whether 2xx appears without session cookies              |
| A-5 | **Port & protocol exposure**       | Standard 80/443 vs non-standard ports, HTTP/2, WebSocket                 | Nmap / service banner                                    |

---

## B. Technology Fingerprint

| #   | Filter                              | What you measure                            | Typical signal                                       |
| --- | ----------------------------------- | ------------------------------------------- | ---------------------------------------------------- |
| B-1 | **Underlying product / framework**  | CMS, vendor gateway, custom stack           | Wappalyzer + favicon hash                            |
| B-2 | **Historical CVE density**          | Known vuln history of that product          | CVE count last 3 yrs × CVSS                          |
| B-3 | **Modern compiled / obfuscated JS** | Presence of webpack chunks / source maps    | - Minified/hashed file names<br>- JS bundle > 200 kB |
| B-4 | **Response format**                 | HTML vs JSON vs **XML** (high-value for GP) | Top-level `Content-Type`                             |
| B-5 | **TLS / cipher hygiene**            | Weak ciphers, expired certs                 | SSLyze grade                                         |

---

## C. Security Controls in Front

| #   | Filter                               | What you measure                    | Typical signal                           |
| --- | ------------------------------------ | ----------------------------------- | ---------------------------------------- |
| C-1 | **WAF / CDN presence**               | Cloudflare, Akamai, AWS WAF, F5 ASM | HTTP headers, IP ASN, TLS JA3            |
| C-2 | **Rate-limit behaviour**             | Does burst of 50 r/s trigger 429?   | Synthetic traffic burst                  |
| C-3 | **Content-Security-Policy strength** | Strict, report-only, or none        | `Content-Security-Policy` header parsing |
| C-4 | **Anti-automation banners**          | CAPTCHA, JS challenge, bot-block    | Selenium test + DOM check                |

---

## D. Content & Similarity-Based Deduplication

| #   | Filter                         | What you measure                 | Typical signal                            |
| --- | ------------------------------ | -------------------------------- | ----------------------------------------- |
| D-1 | **SimHash / text similarity**  | Mark duplicate staging domains   | 64-bit SimHash over HTML                  |
| D-2 | **Screenshot perceptual hash** | Visually identical login portals | `imagehash.average_hash` on 120 × 120 png |
| D-3 | **Static asset reuse**         | Same JS/CSS across hosts         | Combined SHA-256 of top N assets          |

---

## E. Criticality & Business Impact

| #   | Filter                            | What you measure                             | Typical signal                         |
| --- | --------------------------------- | -------------------------------------------- | -------------------------------------- |
| E-1 | **Asset role**                    | VPN / SSO / payroll / prod API gateway       | Keyword & title regex                  |
| E-2 | **User-interaction requirement**  | Drive-by vs requires click                   | Vulnerability template meta            |
| E-3 | **Data sensitivity / scope tags** | “PII”, “payments”, “prod” labels in H1 scope | Bug-bounty scope text → LLM extraction |

---

## F. Front-end JS Analysis:
- frontend JS includes sites for XSS
"""

response = client.responses.create(
  model="o3",
  input=[
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": CRITERIA
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": """
Given the criteria above for filtering for bug bounty targets, can you return a list of CVEs that match the criteria?
"""
        }
      ]
    }

  ],
  text={
    "format": {
      "type": "text"
    }
  },
  reasoning={
    "effort": "medium"
  },
  tools=[
    {
      "type": "web_search_preview",
      "user_location": {
        "type": "approximate",
        "country": "CA"
      },
      "search_context_size": "medium"
    }
  ],
  store=True
)
print(response)