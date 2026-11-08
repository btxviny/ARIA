package com.aria.chat.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.ClickableText
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    val snackbar = remember { SnackbarHostState() }
    var menuOpen by remember { mutableStateOf(false) }
    var urlDialog by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) {
        vm.attach(it)
    }

    LaunchedEffect(state.messages.size, state.pending) {
        val last = state.messages.size + (if (state.pending) 1 else 0) - 1
        if (last >= 0) listState.animateScrollToItem(last)
    }
    LaunchedEffect(state.notice) {
        state.notice?.let {
            snackbar.showSnackbar(it)
            vm.dismissNotice()
        }
    }

    Scaffold(
        modifier = Modifier.imePadding(),
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            TopAppBar(
                title = { Text("ARIA") },
                actions = {
                    IconButton(onClick = { menuOpen = true }) {
                        Icon(Icons.Default.MoreVert, contentDescription = "Menu")
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        DropdownMenuItem(text = { Text("New chat") }, onClick = {
                            menuOpen = false; vm.newChat()
                        })
                        DropdownMenuItem(text = { Text("Server URL") }, onClick = {
                            menuOpen = false; urlDialog = true
                        })
                        DropdownMenuItem(text = { Text("Test connection") }, onClick = {
                            menuOpen = false; vm.checkConnection()
                        })
                    }
                },
            )
        },
        bottomBar = {
            Column(Modifier.padding(8.dp)) {
                if (state.uploads.isNotEmpty()) {
                    Row(
                        Modifier.fillMaxWidth().padding(bottom = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        // Keep it simple: show the most recent few chips.
                        state.uploads.takeLast(3).forEach { UploadChip(it) }
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { picker.launch(arrayOf("*/*")) }) {
                        Icon(Icons.Default.AttachFile, contentDescription = "Attach files")
                    }
                    OutlinedTextField(
                        value = state.input,
                        onValueChange = vm::onInputChange,
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Ask ARIA…") },
                        maxLines = 5,
                    )
                    IconButton(
                        onClick = vm::send,
                        enabled = state.input.isNotBlank() && !state.pending,
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Send")
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.messages) { MessageBubble(it) }
            if (state.pending) {
                item { CircularProgressIndicator(Modifier.padding(8.dp).size(24.dp)) }
            }
        }
    }

    if (urlDialog) {
        var text by remember { mutableStateOf(state.baseUrl) }
        AlertDialog(
            onDismissRequest = { urlDialog = false },
            title = { Text("Server URL") },
            text = {
                OutlinedTextField(value = text, onValueChange = { text = it }, singleLine = true)
            },
            confirmButton = {
                TextButton(onClick = { vm.setServerUrl(text); urlDialog = false }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { urlDialog = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun UploadChip(item: UploadItem) {
    val label = when (item.status) {
        UploadStatus.UPLOADING -> "${item.name} …"
        UploadStatus.DONE -> "${item.name} ✓"
        UploadStatus.FAILED -> "${item.name} ✗ ${item.detail.orEmpty()}"
    }
    AssistChip(onClick = {}, label = { Text(label, maxLines = 1) }, modifier = Modifier.widthIn(max = 160.dp))
}

@Composable
private fun MessageBubble(msg: ChatMessage) {
    val uriHandler = LocalUriHandler.current
    val color = when {
        msg.isError -> MaterialTheme.colorScheme.errorContainer
        msg.fromUser -> MaterialTheme.colorScheme.primaryContainer
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    Box(Modifier.fillMaxWidth(), contentAlignment = if (msg.fromUser) Alignment.CenterEnd else Alignment.CenterStart) {
        Surface(color = color, shape = RoundedCornerShape(12.dp), modifier = Modifier.widthIn(max = 320.dp)) {
            Column(Modifier.padding(10.dp)) {
                Text(msg.text)
                msg.files.forEach { f ->
                    val styled = AnnotatedString(
                        f.name,
                        SpanStyle(color = MaterialTheme.colorScheme.primary, textDecoration = TextDecoration.Underline),
                    )
                    ClickableText(
                        text = styled,
                        modifier = Modifier.padding(top = 6.dp),
                        onClick = { runCatching { uriHandler.openUri(f.url) } },
                    )
                }
            }
        }
    }
}
