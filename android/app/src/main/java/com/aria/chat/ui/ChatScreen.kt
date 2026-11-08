package com.aria.chat.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    val snackbar = remember { SnackbarHostState() }
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
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

    fun closeDrawer(action: () -> Unit) {
        action()
        scope.launch { drawer.close() }
    }

    ModalNavigationDrawer(
        drawerState = drawer,
        drawerContent = {
            ModalDrawerSheet(drawerContainerColor = MaterialTheme.colorScheme.surfaceContainer) {
                Text("ARIA", fontSize = 22.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(horizontal = 24.dp, vertical = 20.dp))
                NavigationDrawerItem(
                    label = { Text("New chat") },
                    icon = { Icon(Icons.Default.Add, null) },
                    selected = false,
                    onClick = { closeDrawer { vm.newChat() } },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                Text("Recents", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 28.dp, top = 16.dp, bottom = 4.dp))
                LazyColumn(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                    items(state.sessions, key = { it.threadId }) { s ->
                        NavigationDrawerItem(
                            label = {
                                Text(s.title.ifBlank { "Untitled chat" }, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            },
                            selected = s.threadId == state.threadId,
                            onClick = { closeDrawer { vm.openSession(s.threadId) } },
                            badge = {
                                IconButton(onClick = { vm.deleteSession(s.threadId) }, modifier = Modifier.size(32.dp)) {
                                    Icon(Icons.Default.Delete, "Delete chat", modifier = Modifier.size(18.dp))
                                }
                            },
                        )
                    }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                NavigationDrawerItem(
                    label = { Text("Server URL") },
                    icon = { Icon(Icons.Default.Settings, null) },
                    selected = false,
                    onClick = { closeDrawer { urlDialog = true } },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                NavigationDrawerItem(
                    label = { Text("Test connection") },
                    icon = { Icon(Icons.Default.Wifi, null) },
                    selected = false,
                    onClick = { closeDrawer { vm.checkConnection() } },
                    modifier = Modifier.padding(horizontal = 12.dp).padding(bottom = 8.dp),
                )
            }
        },
    ) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            contentWindowInsets = WindowInsets(0, 0, 0, 0),
            snackbarHost = { SnackbarHost(snackbar) },
            topBar = {
                TopAppBar(
                    title = { Text(state.title, maxLines = 1, overflow = TextOverflow.Ellipsis, fontSize = 18.sp) },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawer.open() } }) {
                            Icon(Icons.Default.Menu, "Chats")
                        }
                    },
                    actions = {
                        IconButton(onClick = vm::newChat) { Icon(Icons.Default.Add, "New chat") }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                )
            },
            bottomBar = {
                InputBar(
                    state = state,
                    onInput = vm::onInputChange,
                    onSend = vm::send,
                    onAttach = { picker.launch(arrayOf("*/*")) },
                )
            },
        ) { padding ->
            if (state.messages.isEmpty() && !state.pending) {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    Text("How can I help?", fontSize = 26.sp, fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    items(state.messages) { MessageItem(it) }
                    if (state.pending) {
                        item { CircularProgressIndicator(Modifier.padding(4.dp).size(22.dp), strokeWidth = 2.5.dp) }
                    }
                }
            }
        }
    }

    if (urlDialog) {
        var text by remember { mutableStateOf(state.baseUrl) }
        AlertDialog(
            onDismissRequest = { urlDialog = false },
            title = { Text("Server URL") },
            text = { OutlinedTextField(value = text, onValueChange = { text = it }, singleLine = true) },
            confirmButton = { TextButton(onClick = { vm.setServerUrl(text); urlDialog = false }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { urlDialog = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun InputBar(state: ChatUiState, onInput: (String) -> Unit, onSend: () -> Unit, onAttach: () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.background,
        modifier = Modifier.navigationBarsPadding().imePadding(),
    ) {
        Surface(
            shape = RoundedCornerShape(28.dp),
            color = MaterialTheme.colorScheme.surfaceContainer,
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            Column {
                if (state.uploads.isNotEmpty()) {
                    Row(
                        Modifier.horizontalScroll(rememberScrollState()).padding(start = 12.dp, top = 8.dp, end = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) { state.uploads.forEach { UploadChip(it) } }
                }
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(horizontal = 4.dp)) {
                    IconButton(onClick = onAttach) { Icon(Icons.Default.AttachFile, "Attach files") }
                    TextField(
                        value = state.input,
                        onValueChange = onInput,
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Message ARIA") },
                        maxLines = 6,
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = Color.Transparent,
                            unfocusedContainerColor = Color.Transparent,
                            focusedIndicatorColor = Color.Transparent,
                            unfocusedIndicatorColor = Color.Transparent,
                        ),
                    )
                    FilledIconButton(
                        onClick = onSend,
                        enabled = state.input.isNotBlank() && !state.pending,
                        modifier = Modifier.padding(end = 4.dp).size(40.dp),
                    ) { Icon(Icons.Default.ArrowUpward, "Send") }
                }
            }
        }
    }
}

@Composable
private fun UploadChip(item: UploadItem) {
    val label = when (item.status) {
        UploadStatus.UPLOADING -> "${item.name} …"
        UploadStatus.DONE -> "${item.name} ✓"
        UploadStatus.FAILED -> "${item.name} ✗ ${item.detail.orEmpty()}"
    }
    AssistChip(onClick = {}, label = { Text(label, maxLines = 1) }, modifier = Modifier.widthIn(max = 220.dp))
}

@Composable
private fun MessageItem(msg: ChatMessage) {
    if (msg.fromUser) {
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier.widthIn(max = 300.dp),
            ) { Text(msg.text, Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) }
        }
        return
    }
    // Assistant: plain text on the background, ChatGPT/Claude style.
    Column(Modifier.fillMaxWidth()) {
        if (msg.isError) {
            Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(12.dp)) {
                Text(msg.text, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onErrorContainer)
            }
        } else {
            MarkdownText(msg.text)
        }
        val uriHandler = LocalUriHandler.current
        msg.files.forEach { f ->
            if (f.isImage) {
                AsyncImage(
                    model = f.url,
                    contentDescription = f.name,
                    contentScale = ContentScale.FillWidth,
                    modifier = Modifier.padding(top = 10.dp).fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .clickable { runCatching { uriHandler.openUri(f.url) } },
                )
            } else {
                Text(
                    buildAnnotatedString {
                        withStyle(SpanStyle(color = MaterialTheme.colorScheme.primary, textDecoration = TextDecoration.Underline)) {
                            append("⬇ ${f.name}")
                        }
                    },
                    modifier = Modifier.padding(top = 8.dp).clickable { runCatching { uriHandler.openUri(f.url) } },
                )
            }
        }
    }
}
