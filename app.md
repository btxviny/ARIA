# Android (Kotlin) chat client for the ARIA API

## Context
ARIA is a FastAPI + Celery multi-agent chatbot. This adds a simple Android app
(in `android/`) that chats with the API at `http://100.91.177.31:5000` over Tailscale
and can upload files. No server changes are needed.

## API contract the app must follow
(verified in `src/routers/*` and `src/schemas.py`)

- Chat is async: `POST /question/` `{prompt, thread_id}` -> `{task_id}`; poll
  `GET /answer/{task_id}` -> `{status: "Pending"|"Completed"|"Failed", result, error}`.
  `result` = `{answer, thread_id, code_files, code_run_id, code_result, web_result_cards}`.
- Uploads are JSON + base64, not multipart: `{thread_id, files:[{filename, content_base64}]}`.
  - `POST /sources/upload` (RAG documents) -> `{tasks:[{filename, task_id}]}`; poll each via `/answer/{task_id}`.
  - `POST /datafiles/upload` (`.xlsx .xls .csv .json .parquet .tsv`, for the code executor) -> saved immediately, returns the file list.
  - 15 MB limit per file (`MAX_UPLOAD_MB`); the server returns 413 when exceeded.
- The same `thread_id` means the same conversation memory and the same uploaded files, so the app keeps one per chat.
- Generated files: `GET /files/{run_id}/{filename}`. Connectivity check: `GET /health`.

## Design
Single-module app: Jetpack Compose + Material 3, Retrofit + OkHttp + kotlinx-serialization,
ViewModel/StateFlow, coroutines. No DI framework, no database.

Package `com.aria.chat`, under `android/`:

- Gradle: `settings.gradle.kts`, `build.gradle.kts`, `gradle/libs.versions.toml`, `app/build.gradle.kts`, wrapper (generated with the installed Gradle).
- `AndroidManifest.xml`: `INTERNET` permission and `networkSecurityConfig`.
- `res/xml/network_security_config.xml`: Android 9+ blocks plain HTTP and the API is HTTP, so allow cleartext (traffic already runs inside Tailscale's WireGuard tunnel).
- `data/AriaApi.kt`, `data/Models.kt`, `data/AriaRepository.kt`: Retrofit interface, DTOs mirroring the schemas, send + poll (~1.5 s interval, with a ceiling), upload + poll, health check. Long work is polled, not held open, so a ~30 s read timeout is fine.
- `ui/ChatViewModel.kt`: messages, input, pending state, uploaded files, `thread_id` (UUID; "New chat" makes a fresh one), base URL persisted in SharedPreferences (default `http://100.91.177.31:5000`).
- `ui/ChatScreen.kt`: message bubbles, text field + send, attach button (`OpenMultipleDocuments`), upload status chips, menu with "New chat" and "Server URL", and tappable links for generated `code_files` (opens `/files/{run_id}/{filename}` in the browser).
- `util/FileUtils.kt`: read bytes via `ContentResolver`, filename via `OpenableColumns`, base64 (`NO_WRAP`), reject files over 15 MB before encoding.
- Upload routing by extension: data-file extensions go to `/datafiles/upload`, everything else to `/sources/upload`. The supported document types come from `src/rag/ingest.py`, so unsupported files get a clear error.
- `android/README.md` (open in Android Studio, build/install, change URL, Tailscale note) and `android/.gitignore` (`build/`, `.gradle/`, `local.properties`).

## Verification
1. If an Android SDK can be obtained in the sandbox, run `gradle assembleDebug` and `lint` in `android/`. If not, say so plainly and leave compile verification to Android Studio.
2. Re-check DTO field names and paths against `src/schemas.py` and the routers.
3. On the phone, with Tailscale on:
   - Open `http://100.91.177.31:5000/health` in the browser (expects `{"status":"ok"}`).
   - Install the app and send a message.
   - Attach a CSV (goes to datafiles) and a PDF or text file (goes to sources), then ask about them.

## Notes and assumptions
- The API must listen on `0.0.0.0`. docker-compose already does (`uvicorn ... --host 0.0.0.0 --port 5000`).
- The API has no auth today; Tailscale is the access boundary.
- Work is committed and pushed to `ccr-edb09a89-196egj` only. No PR unless requested.
