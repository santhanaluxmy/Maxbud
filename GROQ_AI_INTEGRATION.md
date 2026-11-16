# Groq integration — November 15, 2026

`app/services/ai.py` uses the installed Groq SDK (1.7.0), environment-only `GROQ_API_KEY`, `GROQ_CHAT_MODEL`, `GROQ_VISION_MODEL`. The configured model IDs were checked against the live models API: `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`. Availability can change; recheck for deployment. Official references: [Groq models](https://console.groq.com/docs/models), [vision](https://console.groq.com/docs/vision).

## Receipt flow

`GET /ai/categories` loads the caller's actual expense categories from categories, personal budgets and recorded personal expenses. No model-invented categories are created. `POST /ai/receipts` requires authentication, existing categories, successful-image validation, JPEG/PNG MIME and actual content, <=5 MB, decompression-bomb protection and per-user quota. Images are EXIF-normalized, resized, private random-name JPEG files with directory/file permissions 0700/0600. Storage is outside frontend public assets; no filesystem path is returned.

Groq receives the normalized image and permitted categories. JSON mode, Decimal parsing and Pydantic validate merchant/date/total/currency/category and nullable line-item values. Tamil/English text is requested. Missing grand totals remain `total=null`, `printed_total=null`; `calculated_subtotal` is distinct. Unreadable text stays null. Ambiguous currency such as “Rs.” is normalized to null for explicit user review, without assuming LKR. Required JSON keys and a permitted-category enum guide extraction. Invalid extraction/provider failures consume no successful scan credit; accepted extraction consumes one scan even before confirmation. Image hashes prevent repeated uploads consuming another credit.

The existing React scanner uploads the selected file directly. Every result is editable. `POST /ai/receipts/{id}/confirm` requires owner, explicit reviewed total/date/merchant/category/currency and a usable personal account. It preserves original extraction, creates exactly one expense, links the scan, and updates balances/budget queries. Repeated confirmation returns the same transaction. It cannot save into another person's account. User review, not OCR certainty, determines the final financial amount.

## Advisor

`GET /ai/advisor` returns only the caller's history. `POST /ai/advisor` sends current private dashboard totals, category spending, budgets, tracked balance, safe-to-spend, active personal goals, upcoming bills, trends and three prior exchanges. It never pools family salaries or exposes account identifiers/passwords/keys. `(user_id,request_id)` uniqueness and matching-question checks prevent duplicate successful messages. Monthly quotas are per user, including sponsored members. English/Tamil/Tanglish instructions are supported.

No AI tools, generated commands or write execution exist. Receipt/question/history strings are untrusted input; system instructions restrict advice to supplied totals and explain missing data. This reduces prompt-injection impact, but model prose is still probabilistic and requires human judgment.

## Failure handling and tests

45-second timeout, no automatic retries, bounded output/history. Timeout/rate/provider/malformed JSON return sanitized retryable messages; successful usage is not charged. Platform events record feature/status only, not images, prompts, financial contents or provider keys. Database failures do not persist partial scans/transactions.

Mocked failure/security/quota tests live in `test_features.py` and `test_beta.py`. Opt-in `tests/live_groq.py` uses the real provider and outer-rollback MySQL; `tests/beta_browser.py` uses real frontend upload/provider with a temporary SQLite database. These consume actual provider requests and never run at pytest discovery. Standalone developer scripts/sample receipt are retained as reviewed test assets. See TEST_REPORT for actual live outcomes; mocks are not live evidence.
