package com.aria.chat.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aria.chat.data.AriaException
import com.aria.chat.data.AriaRepository
import com.aria.chat.data.SessionInfo
import com.aria.chat.util.UploadKind
import com.aria.chat.util.displayName
import com.aria.chat.util.readPayload
import com.aria.chat.util.uploadKind
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.UUID

data class GeneratedFile(val name: String, val url: String) {
    val isImage: Boolean
        get() = name.substringAfterLast('.', "").lowercase() in setOf("png", "jpg", "jpeg", "gif", "webp")
}

data class ChatMessage(
    val fromUser: Boolean,
    val text: String,
    val files: List<GeneratedFile> = emptyList(),
    val isError: Boolean = false,
)

enum class UploadStatus { UPLOADING, DONE, FAILED }

data class UploadItem(
    val id: Long,
    val name: String,
    val status: UploadStatus,
    val detail: String? = null,
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    val pending: Boolean = false,
    val uploads: List<UploadItem> = emptyList(),
    val threadId: String = UUID.randomUUID().toString(),
    val baseUrl: String = AriaRepository.DEFAULT_URL,
    val notice: String? = null,
    val sessions: List<SessionInfo> = emptyList(),
)

val ChatUiState.title: String
    get() = sessions.firstOrNull { it.threadId == threadId }?.title?.takeIf { it.isNotBlank() } ?: "New chat"

class ChatViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.getSharedPreferences("aria", 0)
    private val repo = AriaRepository(prefs.getString(KEY_URL, null) ?: AriaRepository.DEFAULT_URL)
    private var nextUploadId = 0L

    private val _state = MutableStateFlow(ChatUiState(baseUrl = repo.baseUrl.trimEnd('/')))
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    init {
        refreshSessions()
    }

    fun refreshSessions() {
        viewModelScope.launch {
            try {
                val list = repo.sessions()
                _state.update { it.copy(sessions = list) }
            } catch (_: AriaException) {
                // History is optional; ignore (server may be unreachable or have no DB).
            }
        }
    }

    fun openSession(threadId: String) {
        if (threadId == _state.value.threadId) return
        _state.update {
            it.copy(threadId = threadId, messages = emptyList(), uploads = emptyList(), pending = true, input = "")
        }
        viewModelScope.launch {
            try {
                val msgs = repo.messages(threadId).map { m ->
                    ChatMessage(m.role == "user", m.content, toFiles(m.codeRunId, m.codeFiles))
                }
                _state.update { if (it.threadId == threadId) it.copy(messages = msgs, pending = false) else it }
            } catch (e: AriaException) {
                _state.update {
                    if (it.threadId != threadId) it
                    else it.copy(pending = false, messages = listOf(ChatMessage(false, e.message ?: "Failed to load chat", isError = true)))
                }
            }
        }
    }

    fun deleteSession(threadId: String) {
        viewModelScope.launch {
            try {
                repo.deleteSession(threadId)
                if (threadId == _state.value.threadId) newChat()
                refreshSessions()
            } catch (e: AriaException) {
                _state.update { it.copy(notice = e.message) }
            }
        }
    }

    private fun toFiles(runId: String?, files: List<kotlinx.serialization.json.JsonObject>?): List<GeneratedFile> {
        if (runId.isNullOrEmpty()) return emptyList()
        return files.orEmpty().mapNotNull { f ->
            AriaRepository.fileName(f)?.let { name ->
                GeneratedFile(name, "${repo.baseUrl}files/${Uri.encode(runId)}/${Uri.encode(name)}")
            }
        }
    }

    fun onInputChange(text: String) = _state.update { it.copy(input = text) }

    fun dismissNotice() = _state.update { it.copy(notice = null) }

    fun newChat() = _state.update {
        ChatUiState(baseUrl = it.baseUrl, sessions = it.sessions, threadId = UUID.randomUUID().toString())
    }

    fun setServerUrl(url: String) {
        repo.setBaseUrl(url)
        val saved = repo.baseUrl.trimEnd('/')
        prefs.edit().putString(KEY_URL, saved).apply()
        _state.update { it.copy(baseUrl = saved) }
    }

    fun checkConnection() = viewModelScope.launch {
        val msg = try {
            if (repo.health()) "Connected to ${repo.baseUrl}" else "Server responded, but not healthy"
        } catch (e: AriaException) {
            e.message ?: "Connection failed"
        }
        _state.update { it.copy(notice = msg) }
    }

    fun send() {
        val s = _state.value
        val prompt = s.input.trim()
        if (prompt.isEmpty() || s.pending) return
        val thread = s.threadId
        _state.update {
            it.copy(messages = it.messages + ChatMessage(true, prompt), input = "", pending = true)
        }
        viewModelScope.launch {
            val reply = try {
                val r = repo.ask(prompt, thread)
                val files = toFiles(r.codeRunId, r.codeFiles)
                ChatMessage(false, r.answer.orEmpty().ifBlank { "(empty answer)" }, files)
            } catch (e: AriaException) {
                ChatMessage(false, e.message ?: "Request failed", isError = true)
            }
            // Ignore the reply if the user started a new chat meanwhile.
            _state.update {
                if (it.threadId != thread) it else it.copy(messages = it.messages + reply, pending = false)
            }
            refreshSessions()
        }
    }

    fun attach(uris: List<Uri>) {
        val thread = _state.value.threadId
        val ctx = getApplication<Application>()
        for (uri in uris) {
            val id = nextUploadId++
            viewModelScope.launch {
                val name = withContext(Dispatchers.IO) { displayName(ctx, uri) }
                setUpload(thread, UploadItem(id, name, UploadStatus.UPLOADING))
                try {
                    val kind = uploadKind(name)
                    val payload = withContext(Dispatchers.IO) { readPayload(ctx, uri, name) }
                    when (kind) {
                        UploadKind.DATA -> repo.uploadDataFiles(thread, listOf(payload))
                        UploadKind.SOURCE -> {
                            val task = repo.uploadSources(thread, listOf(payload)).first()
                            repo.awaitResult(task.taskId)
                        }
                    }
                    setUpload(thread, UploadItem(id, name, UploadStatus.DONE))
                } catch (e: Exception) {
                    // AriaException, UnsupportedFileException, IO errors
                    setUpload(thread, UploadItem(id, name, UploadStatus.FAILED, e.message))
                }
            }
        }
    }

    private fun setUpload(thread: String, item: UploadItem) = _state.update { s ->
        if (s.threadId != thread) s
        else s.copy(
            uploads = if (s.uploads.any { it.id == item.id })
                s.uploads.map { if (it.id == item.id) item else it }
            else s.uploads + item
        )
    }

    private companion object {
        const val KEY_URL = "base_url"
    }
}
