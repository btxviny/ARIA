package com.aria.chat.data

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.coroutines.delay
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import java.io.IOException
import java.util.concurrent.TimeUnit

class AriaException(message: String) : Exception(message)

class AriaRepository(initialBaseUrl: String) {

    private val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }

    // Long work is polled, so a modest read timeout is enough.
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    var baseUrl: String = normalize(initialBaseUrl)
        private set
    private var api: AriaApi = buildApi(baseUrl)

    fun setBaseUrl(url: String) {
        baseUrl = normalize(url)
        api = buildApi(baseUrl)
    }

    private fun buildApi(url: String): AriaApi =
        Retrofit.Builder()
            .baseUrl(url)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AriaApi::class.java)

    suspend fun health(): Boolean = call { api.health().status == "ok" }

    /** Sends a question and polls until the task finishes. */
    suspend fun ask(prompt: String, threadId: String): ChatResult {
        val taskId = call { api.question(ChatRequest(prompt, threadId)).taskId }
        return awaitResult(taskId)
    }

    /** Uploads data files (code executor). Saved immediately by the server. */
    suspend fun uploadDataFiles(threadId: String, files: List<FilePayload>) {
        call { api.uploadDataFiles(UploadRequest(threadId, files)) }
    }

    /** Uploads RAG documents; returns one ingest task per file. */
    suspend fun uploadSources(threadId: String, files: List<FilePayload>): List<SourceUploadTask> =
        call { api.uploadSources(UploadRequest(threadId, files)).tasks }

    suspend fun awaitResult(taskId: String): ChatResult {
        repeat(MAX_POLLS) {
            val r = call { api.answer(taskId) }
            when (r.status) {
                "Completed" -> return r.result ?: ChatResult()
                "Failed" -> throw AriaException(r.error ?: "Task failed")
            }
            delay(POLL_INTERVAL_MS)
        }
        throw AriaException("Timed out waiting for the server")
    }

    private suspend fun <T> call(block: suspend () -> T): T = try {
        block()
    } catch (e: HttpException) {
        throw AriaException(httpMessage(e))
    } catch (e: IOException) {
        throw AriaException("Cannot reach server at $baseUrl (is Tailscale on?)")
    }

    private fun httpMessage(e: HttpException): String {
        val detail = try {
            val body = e.response()?.errorBody()?.string().orEmpty()
            val d = json.parseToJsonElement(body).jsonObject["detail"]
            d?.let { runCatching { it.jsonPrimitive.content }.getOrDefault(it.toString()) }
        } catch (_: Exception) {
            null
        }
        return when (e.code()) {
            413 -> detail ?: "File too large for the server"
            else -> detail ?: "Server error ${e.code()}"
        }
    }

    companion object {
        const val DEFAULT_URL = "http://100.91.177.31:5000"
        private const val POLL_INTERVAL_MS = 1500L
        private const val MAX_POLLS = 400 // ~10 minutes

        fun normalize(url: String): String {
            val t = url.trim().ifEmpty { DEFAULT_URL }
            val withScheme = if (t.startsWith("http://") || t.startsWith("https://")) t else "http://$t"
            return withScheme.trimEnd('/') + "/"
        }

        /** Parses `filename` out of a code_files entry. */
        fun fileName(entry: JsonObject): String? =
            entry["filename"]?.let { runCatching { it.jsonPrimitive.content }.getOrNull() }
    }
}
