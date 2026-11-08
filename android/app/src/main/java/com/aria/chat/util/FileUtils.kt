package com.aria.chat.util

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import com.aria.chat.data.FilePayload

const val MAX_UPLOAD_BYTES = 15L * 1024 * 1024

// Mirrors src/routers/datafiles.py ACCEPTED_EXTENSIONS and src/rag/ingest.py SUPPORTED_EXTENSIONS.
val DATA_EXTENSIONS = setOf("xlsx", "xls", "csv", "json", "parquet", "tsv")
val DOCUMENT_EXTENSIONS = setOf("pdf", "txt", "md")

enum class UploadKind { DATA, SOURCE }

class UnsupportedFileException(message: String) : Exception(message)

fun uploadKind(filename: String): UploadKind {
    val ext = filename.substringAfterLast('.', "").lowercase()
    return when (ext) {
        in DATA_EXTENSIONS -> UploadKind.DATA
        in DOCUMENT_EXTENSIONS -> UploadKind.SOURCE
        else -> throw UnsupportedFileException(
            "Unsupported type '.$ext'. Data: ${DATA_EXTENSIONS.sorted().joinToString()}; " +
                "documents: ${DOCUMENT_EXTENSIONS.sorted().joinToString()}"
        )
    }
}

fun displayName(context: Context, uri: Uri): String =
    query(context, uri, OpenableColumns.DISPLAY_NAME)?.takeIf { it.isNotBlank() }
        ?: uri.lastPathSegment?.substringAfterLast('/')
        ?: "file"

/** Reads the file and base64-encodes it, rejecting anything over 15 MB before encoding. */
fun readPayload(context: Context, uri: Uri, filename: String): FilePayload {
    val declared = query(context, uri, OpenableColumns.SIZE)?.toLongOrNull()
    if (declared != null && declared > MAX_UPLOAD_BYTES) throw tooLarge(filename)

    val stream = context.contentResolver.openInputStream(uri)
        ?: throw UnsupportedFileException("Cannot open $filename")
    val bytes = stream.use { input ->
        val out = java.io.ByteArrayOutputStream()
        val buf = ByteArray(64 * 1024)
        var total = 0L
        while (true) {
            val n = input.read(buf)
            if (n < 0) break
            total += n
            if (total > MAX_UPLOAD_BYTES) throw tooLarge(filename)
            out.write(buf, 0, n)
        }
        out.toByteArray()
    }
    return FilePayload(filename, Base64.encodeToString(bytes, Base64.NO_WRAP))
}

private fun tooLarge(name: String) = UnsupportedFileException("'$name' exceeds the 15 MB limit")

private fun query(context: Context, uri: Uri, column: String): String? =
    context.contentResolver.query(uri, arrayOf(column), null, null, null)?.use { c ->
        if (c.moveToFirst()) {
            val i = c.getColumnIndex(column)
            if (i >= 0 && !c.isNull(i)) c.getString(i) else null
        } else null
    }
