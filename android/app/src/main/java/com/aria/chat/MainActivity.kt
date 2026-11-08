package com.aria.chat

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.aria.chat.ui.AriaTheme
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aria.chat.ui.ChatScreen
import com.aria.chat.ui.ChatViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AriaTheme {
                ChatScreen(viewModel<ChatViewModel>())
            }
        }
    }
}
