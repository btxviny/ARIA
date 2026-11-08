package com.aria.chat.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface AriaApi {
    @POST("question/")
    suspend fun question(@Body body: ChatRequest): ChatResponse

    @GET("answer/{taskId}")
    suspend fun answer(@Path("taskId") taskId: String): AnswerResponse

    @POST("sources/upload")
    suspend fun uploadSources(@Body body: UploadRequest): SourceUploadResponse

    @POST("datafiles/upload")
    suspend fun uploadDataFiles(@Body body: UploadRequest): DataFilesResponse

    @GET("health")
    suspend fun health(): HealthResponse

    @GET("sessions")
    suspend fun sessions(@retrofit2.http.Query("limit") limit: Int = 100): List<SessionInfo>

    @GET("sessions/{threadId}/messages")
    suspend fun messages(@Path("threadId") threadId: String): List<MessageInfo>

    @DELETE("sessions/{threadId}")
    suspend fun deleteSession(@Path("threadId") threadId: String): Response<Unit>
}
