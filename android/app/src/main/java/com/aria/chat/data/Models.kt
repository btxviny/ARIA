package com.aria.chat.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class ChatRequest(val prompt: String, @SerialName("thread_id") val threadId: String)

@Serializable
data class ChatResponse(@SerialName("task_id") val taskId: String)

@Serializable
data class AnswerResponse(
    val status: String,
    val result: ChatResult? = null,
    val error: String? = null,
)

/** `result` of a chat task. Ingest tasks return a different dict; every field is optional. */
@Serializable
data class ChatResult(
    val answer: String? = null,
    @SerialName("thread_id") val threadId: String? = null,
    @SerialName("code_files") val codeFiles: List<JsonObject>? = null,
    @SerialName("code_run_id") val codeRunId: String? = null,
    @SerialName("code_result") val codeResult: String? = null,
    @SerialName("web_result_cards") val webResultCards: List<JsonObject>? = null,
)

@Serializable
data class FilePayload(
    val filename: String,
    @SerialName("content_base64") val contentBase64: String,
)

@Serializable
data class UploadRequest(
    @SerialName("thread_id") val threadId: String,
    val files: List<FilePayload>,
)

@Serializable
data class SourceUploadTask(val filename: String, @SerialName("task_id") val taskId: String)

@Serializable
data class SourceUploadResponse(val tasks: List<SourceUploadTask>)

@Serializable
data class DataFileInfo(val filename: String, @SerialName("size_bytes") val sizeBytes: Long)

@Serializable
data class DataFilesResponse(val files: List<DataFileInfo>)

@Serializable
data class HealthResponse(val status: String)

@Serializable
data class SessionInfo(
    @SerialName("thread_id") val threadId: String,
    val title: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
    @SerialName("message_count") val messageCount: Int = 0,
)

@Serializable
data class MessageInfo(
    val role: String,
    val content: String = "",
    @SerialName("code_run_id") val codeRunId: String? = null,
    @SerialName("code_files") val codeFiles: List<JsonObject>? = null,
)
