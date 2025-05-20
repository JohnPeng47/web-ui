SERVER_SIDE = {
  "sql_injection": [
    {
      "link": "/web-security/sql-injection/lab-retrieve-hidden-data",
      "name": "SQL injection vulnerability in WHERE clause allowing retrieval of hidden data"
    },
    {
      "link": "/web-security/sql-injection/lab-login-bypass",
      "name": "SQL injection vulnerability allowing login bypass"
    },
    {
      "link": "/web-security/sql-injection/examining-the-database/lab-querying-database-version-oracle",
      "name": "SQL injection attack, querying the database type and version on Oracle"
    },
    {
      "link": "/web-security/sql-injection/examining-the-database/lab-querying-database-version-mysql-microsoft",
      "name": "SQL injection attack, querying the database type and version on MySQL and Microsoft"
    },
    {
      "link": "/web-security/sql-injection/examining-the-database/lab-listing-database-contents-non-oracle",
      "name": "SQL injection attack, listing the database contents on non-Oracle databases"
    },
    {
      "link": "/web-security/sql-injection/examining-the-database/lab-listing-database-contents-oracle",
      "name": "SQL injection attack, listing the database contents on Oracle"
    },
    {
      "link": "/web-security/sql-injection/union-attacks/lab-determine-number-of-columns",
      "name": "SQL injection UNION attack, determining the number of columns returned by the query"
    },
    {
      "link": "/web-security/sql-injection/union-attacks/lab-find-column-containing-text",
      "name": "SQL injection UNION attack, finding a column containing text"
    },
    {
      "link": "/web-security/sql-injection/union-attacks/lab-retrieve-data-from-other-tables",
      "name": "SQL injection UNION attack, retrieving data from other tables"
    },
    {
      "link": "/web-security/sql-injection/union-attacks/lab-retrieve-multiple-values-in-single-column",
      "name": "SQL injection UNION attack, retrieving multiple values in a single column"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-conditional-responses",
      "name": "Blind SQL injection with conditional responses"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-conditional-errors",
      "name": "Blind SQL injection with conditional errors"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-sql-injection-visible-error-based",
      "name": "Visible error-based SQL injection"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-time-delays",
      "name": "Blind SQL injection with time delays"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-time-delays-info-retrieval",
      "name": "Blind SQL injection with time delays and information retrieval"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-out-of-band",
      "name": "Blind SQL injection with out-of-band interaction"
    },
    {
      "link": "/web-security/sql-injection/blind/lab-out-of-band-data-exfiltration",
      "name": "Blind SQL injection with out-of-band data exfiltration"
    },
    {
      "link": "/web-security/sql-injection/lab-sql-injection-with-filter-bypass-via-xml-encoding",
      "name": "SQL injection with filter bypass via XML encoding"
    }
  ],
  "authentication": [
    {
      "link": "/web-security/authentication/password-based/lab-username-enumeration-via-different-responses",
      "name": "Username enumeration via different responses"
    },
    {
      "link": "/web-security/authentication/multi-factor/lab-2fa-simple-bypass",
      "name": "2FA simple bypass"
    },
    {
      "link": "/web-security/authentication/other-mechanisms/lab-password-reset-broken-logic",
      "name": "Password reset broken logic"
    },
    {
      "link": "/web-security/authentication/password-based/lab-username-enumeration-via-subtly-different-responses",
      "name": "Username enumeration via subtly different responses"
    },
    {
      "link": "/web-security/authentication/password-based/lab-username-enumeration-via-response-timing",
      "name": "Username enumeration via response timing"
    },
    {
      "link": "/web-security/authentication/password-based/lab-broken-bruteforce-protection-ip-block",
      "name": "Broken brute-force protection, IP block"
    },
    {
      "link": "/web-security/authentication/password-based/lab-username-enumeration-via-account-lock",
      "name": "Username enumeration via account lock"
    },
    {
      "link": "/web-security/authentication/multi-factor/lab-2fa-broken-logic",
      "name": "2FA broken logic"
    },
    {
      "link": "/web-security/authentication/other-mechanisms/lab-brute-forcing-a-stay-logged-in-cookie",
      "name": "Brute-forcing a stay-logged-in cookie"
    },
    {
      "link": "/web-security/authentication/other-mechanisms/lab-offline-password-cracking",
      "name": "Offline password cracking"
    },
    {
      "link": "/web-security/authentication/other-mechanisms/lab-password-reset-poisoning-via-middleware",
      "name": "Password reset poisoning via middleware"
    },
    {
      "link": "/web-security/authentication/other-mechanisms/lab-password-brute-force-via-password-change",
      "name": "Password brute-force via password change"
    },
    {
      "link": "/web-security/authentication/password-based/lab-broken-brute-force-protection-multiple-credentials-per-request",
      "name": "Broken brute-force protection, multiple credentials per request"
    },
    {
      "link": "/web-security/authentication/multi-factor/lab-2fa-bypass-using-a-brute-force-attack",
      "name": "2FA bypass using a brute-force attack"
    }
  ],
  "path_traversal": [
    {
      "link": "/web-security/file-path-traversal/lab-simple",
      "name": "File path traversal, simple case"
    },
    {
      "link": "/web-security/file-path-traversal/lab-absolute-path-bypass",
      "name": "File path traversal, traversal sequences blocked with absolute path bypass"
    },
    {
      "link": "/web-security/file-path-traversal/lab-sequences-stripped-non-recursively",
      "name": "File path traversal, traversal sequences stripped non-recursively"
    },
    {
      "link": "/web-security/file-path-traversal/lab-superfluous-url-decode",
      "name": "File path traversal, traversal sequences stripped with superfluous URL-decode"
    },
    {
      "link": "/web-security/file-path-traversal/lab-validate-start-of-path",
      "name": "File path traversal, validation of start of path"
    },
    {
      "link": "/web-security/file-path-traversal/lab-validate-file-extension-null-byte-bypass",
      "name": "File path traversal, validation of file extension with null byte bypass"
    }
  ],
  "os_command_injection": [
    {
      "link": "/web-security/os-command-injection/lab-simple",
      "name": "OS command injection, simple case"
    },
    {
      "link": "/web-security/os-command-injection/lab-blind-time-delays",
      "name": "Blind OS command injection with time delays"
    },
    {
      "link": "/web-security/os-command-injection/lab-blind-output-redirection",
      "name": "Blind OS command injection with output redirection"
    },
    {
      "link": "/web-security/os-command-injection/lab-blind-out-of-band",
      "name": "Blind OS command injection with out-of-band interaction"
    },
    {
      "link": "/web-security/os-command-injection/lab-blind-out-of-band-data-exfiltration",
      "name": "Blind OS command injection with out-of-band data exfiltration"
    }
  ],
  "business_logic_vulnerabilities": [
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-excessive-trust-in-client-side-controls",
      "name": "Excessive trust in client-side controls"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-high-level",
      "name": "High-level logic vulnerability"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-inconsistent-security-controls",
      "name": "Inconsistent security controls"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-flawed-enforcement-of-business-rules",
      "name": "Flawed enforcement of business rules"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-low-level",
      "name": "Low-level logic flaw"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-inconsistent-handling-of-exceptional-input",
      "name": "Inconsistent handling of exceptional input"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-weak-isolation-on-dual-use-endpoint",
      "name": "Weak isolation on dual-use endpoint"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-insufficient-workflow-validation",
      "name": "Insufficient workflow validation"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-authentication-bypass-via-flawed-state-machine",
      "name": "Authentication bypass via flawed state machine"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-infinite-money",
      "name": "Infinite money logic flaw"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-authentication-bypass-via-encryption-oracle",
      "name": "Authentication bypass via encryption oracle"
    },
    {
      "link": "/web-security/logic-flaws/examples/lab-logic-flaws-bypassing-access-controls-using-email-address-parsing-discrepancies",
      "name": "Bypassing access controls using email address parsing discrepancies"
    }
  ],
  "information_disclosure": [
    {
      "link": "/web-security/information-disclosure/exploiting/lab-infoleak-in-error-messages",
      "name": "Information disclosure in error messages"
    },
    {
      "link": "/web-security/information-disclosure/exploiting/lab-infoleak-on-debug-page",
      "name": "Information disclosure on debug page"
    },
    {
      "link": "/web-security/information-disclosure/exploiting/lab-infoleak-via-backup-files",
      "name": "Source code disclosure via backup files"
    },
    {
      "link": "/web-security/information-disclosure/exploiting/lab-infoleak-authentication-bypass",
      "name": "Authentication bypass via information disclosure"
    },
    {
      "link": "/web-security/information-disclosure/exploiting/lab-infoleak-in-version-control-history",
      "name": "Information disclosure in version control history"
    }
  ],
  "access_control_vulnerabilities": [
    {
      "link": "/web-security/access-control/lab-unprotected-admin-functionality",
      "name": "Unprotected admin functionality"
    },
    {
      "link": "/web-security/access-control/lab-unprotected-admin-functionality-with-unpredictable-url",
      "name": "Unprotected admin functionality with unpredictable URL"
    },
    {
      "link": "/web-security/access-control/lab-user-role-controlled-by-request-parameter",
      "name": "User role controlled by request parameter"
    },
    {
      "link": "/web-security/access-control/lab-user-role-can-be-modified-in-user-profile",
      "name": "User role can be modified in user profile"
    },
    {
      "link": "/web-security/access-control/lab-user-id-controlled-by-request-parameter",
      "name": "User ID controlled by request parameter"
    },
    {
      "link": "/web-security/access-control/lab-user-id-controlled-by-request-parameter-with-unpredictable-user-ids",
      "name": "User ID controlled by request parameter, with unpredictable user IDs"
    },
    {
      "link": "/web-security/access-control/lab-user-id-controlled-by-request-parameter-with-data-leakage-in-redirect",
      "name": "User ID controlled by request parameter with data leakage in redirect"
    },
    {
      "link": "/web-security/access-control/lab-user-id-controlled-by-request-parameter-with-password-disclosure",
      "name": "User ID controlled by request parameter with password disclosure"
    },
    {
      "link": "/web-security/access-control/lab-insecure-direct-object-references",
      "name": "Insecure direct object references"
    },
    {
      "link": "/web-security/access-control/lab-url-based-access-control-can-be-circumvented",
      "name": "URL-based access control can be circumvented"
    },
    {
      "link": "/web-security/access-control/lab-method-based-access-control-can-be-circumvented",
      "name": "Method-based access control can be circumvented"
    },
    {
      "link": "/web-security/access-control/lab-multi-step-process-with-no-access-control-on-one-step",
      "name": "Multi-step process with no access control on one step"
    },
    {
      "link": "/web-security/access-control/lab-referer-based-access-control",
      "name": "Referer-based access control"
    }
  ],
  "file_upload_vulnerabilities": [
    {
      "link": "/web-security/file-upload/lab-file-upload-remote-code-execution-via-web-shell-upload",
      "name": "Remote code execution via web shell upload"
    },
    {
      "link": "/web-security/file-upload/lab-file-upload-web-shell-upload-via-content-type-restriction-bypass",
      "name": "Web shell upload via Content-Type restriction bypass"
    },
    {
      "link": "/web-security/file-upload/lab-file-upload-web-shell-upload-via-path-traversal",
      "name": "Web shell upload via path traversal"
    },
    {
      "link": "/web-security/file-upload/lab-file-upload-web-shell-upload-via-extension-blacklist-bypass",
      "name": "Web shell upload via extension blacklist bypass"
    },
    {
      "link": "/web-security/file-upload/lab-file-upload-web-shell-upload-via-obfuscated-file-extension",
      "name": "Web shell upload via obfuscated file extension"
    },
    {
      "link": "/web-security/file-upload/lab-file-upload-remote-code-execution-via-polyglot-web-shell-upload",
      "name": "Remote code execution via polyglot web shell upload"
    },
    {
      "link": "/web-security/file-upload/lab-file-upload-web-shell-upload-via-race-condition",
      "name": "Web shell upload via race condition"
    }
  ],
  "race_conditions": [
    {
      "link": "/web-security/race-conditions/lab-race-conditions-limit-overrun",
      "name": "Limit overrun race conditions"
    },
    {
      "link": "/web-security/race-conditions/lab-race-conditions-bypassing-rate-limits",
      "name": "Bypassing rate limits via race conditions"
    },
    {
      "link": "/web-security/race-conditions/lab-race-conditions-multi-endpoint",
      "name": "Multi-endpoint race conditions"
    },
    {
      "link": "/web-security/race-conditions/lab-race-conditions-single-endpoint",
      "name": "Single-endpoint race conditions"
    },
    {
      "link": "/web-security/race-conditions/lab-race-conditions-exploiting-time-sensitive-vulnerabilities",
      "name": "Exploiting time-sensitive vulnerabilities"
    },
    {
      "link": "/web-security/race-conditions/lab-race-conditions-partial-construction",
      "name": "Partial construction race conditions"
    }
  ],
  "server_side_request_forgery": [
    {
      "link": "/web-security/ssrf/lab-basic-ssrf-against-localhost",
      "name": "Basic SSRF against the local server"
    },
    {
      "link": "/web-security/ssrf/lab-basic-ssrf-against-backend-system",
      "name": "Basic SSRF against another back-end system"
    },
    {
      "link": "/web-security/ssrf/blind/lab-out-of-band-detection",
      "name": "Blind SSRF with out-of-band detection"
    },
    {
      "link": "/web-security/ssrf/lab-ssrf-with-blacklist-filter",
      "name": "SSRF with blacklist-based input filter"
    },
    {
      "link": "/web-security/ssrf/lab-ssrf-filter-bypass-via-open-redirection",
      "name": "SSRF with filter bypass via open redirection vulnerability"
    },
    {
      "link": "/web-security/ssrf/blind/lab-shellshock-exploitation",
      "name": "Blind SSRF with Shellshock exploitation"
    },
    {
      "link": "/web-security/ssrf/lab-ssrf-with-whitelist-filter",
      "name": "SSRF with whitelist-based input filter"
    }
  ],
  "xml_external_entity_injection": [
    {
      "vuln_request": """
POST /product/stock HTTP/2

<?xml version="1.0" encoding="UTF-8"?><stockCheck><productId>4</productId><storeId>1</storeId></stockCheck>
""", 
      "labs": [
      {
        "link": "/web-security/xxe/lab-exploiting-xxe-to-retrieve-files",
        "name": "Exploiting XXE using external entities to retrieve files"
      },
      {
        "link": "/web-security/xxe/lab-exploiting-xxe-to-perform-ssrf",
        "name": "Exploiting XXE to perform SSRF attacks"
      },
      {
        "link": "/web-security/xxe/blind/lab-xxe-with-out-of-band-interaction",
        "name": "Blind XXE with out-of-band interaction"
      },
      {
        "link": "/web-security/xxe/blind/lab-xxe-with-out-of-band-interaction-using-parameter-entities",
        "name": "Blind XXE with out-of-band interaction via XML parameter entities"
      },
      {
        "link": "/web-security/xxe/blind/lab-xxe-with-out-of-band-exfiltration",
        "name": "Exploiting blind XXE to exfiltrate data using a malicious external DTD"
      },
      {
        "link": "/web-security/xxe/blind/lab-xxe-with-data-retrieval-via-error-messages",
        "name": "Exploiting blind XXE to retrieve data via error messages"
      },
      {
        "link": "/web-security/xxe/lab-xinclude-attack",
        "name": "Exploiting XInclude to retrieve files"
      },
      {
        "link": "/web-security/xxe/lab-xxe-via-file-upload",
        "name": "Exploiting XXE via image file upload"
      },
      {
        "link": "/web-security/xxe/blind/lab-xxe-trigger-error-message-by-repurposing-local-dtd",
        "name": "Exploiting XXE to retrieve data by repurposing a local DTD"
      }
    ]
    }
  ],
  "nosql_injection": [
    {
      "link": "/web-security/nosql-injection/lab-nosql-injection-detection",
      "name": "Detecting NoSQL injection"
    },
    {
      "link": "/web-security/nosql-injection/lab-nosql-injection-bypass-authentication",
      "name": "Exploiting NoSQL operator injection to bypass authentication"
    },
    {
      "link": "/web-security/nosql-injection/lab-nosql-injection-extract-data",
      "name": "Exploiting NoSQL injection to extract data"
    },
    {
      "link": "/web-security/nosql-injection/lab-nosql-injection-extract-unknown-fields",
      "name": "Exploiting NoSQL operator injection to extract unknown fields"
    }
  ],
  "api_testing": [
    {
      "link": "/web-security/api-testing/lab-exploiting-api-endpoint-using-documentation",
      "name": "Exploiting an API endpoint using documentation"
    },
    {
      "link": "/web-security/api-testing/server-side-parameter-pollution/lab-exploiting-server-side-parameter-pollution-in-query-string",
      "name": "Exploiting server-side parameter pollution in a query string"
    },
    {
      "link": "/web-security/api-testing/lab-exploiting-unused-api-endpoint",
      "name": "Finding and exploiting an unused API endpoint"
    },
    {
      "link": "/web-security/api-testing/lab-exploiting-mass-assignment-vulnerability",
      "name": "Exploiting a mass assignment vulnerability"
    },
    {
      "link": "/web-security/api-testing/server-side-parameter-pollution/lab-exploiting-server-side-parameter-pollution-in-rest-url",
      "name": "Exploiting server-side parameter pollution in a REST URL"
    }
  ],
  "web_cache_deception": [
    {
      "link": "/web-security/web-cache-deception/lab-wcd-exploiting-path-mapping",
      "name": "Exploiting path mapping for web cache deception"
    },
    {
      "link": "/web-security/web-cache-deception/lab-wcd-exploiting-path-delimiters",
      "name": "Exploiting path delimiters for web cache deception"
    },
    {
      "link": "/web-security/web-cache-deception/lab-wcd-exploiting-origin-server-normalization",
      "name": "Exploiting origin server normalization for web cache deception"
    },
    {
      "link": "/web-security/web-cache-deception/lab-wcd-exploiting-cache-server-normalization",
      "name": "Exploiting cache server normalization for web cache deception"
    },
    {
      "link": "/web-security/web-cache-deception/lab-wcd-exploiting-exact-match-cache-rules",
      "name": "Exploiting exact-match cache rules for web cache deception"
    }
  ]
}
