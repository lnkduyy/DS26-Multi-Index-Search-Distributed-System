package com.example.recipenode.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;

@Configuration
public class QdrantConfig {

    @Bean(destroyMethod = "close")
    QdrantClient qdrantClient(RecipeNodeProperties properties) {
        var qdrant = properties.qdrant();
        ManagedChannelBuilder<?> channelBuilder = ManagedChannelBuilder.forAddress(qdrant.host(), qdrant.port());

        if (qdrant.tls()) channelBuilder.useTransportSecurity();
        else channelBuilder.usePlaintext();

        ManagedChannel channel = channelBuilder.build();
        QdrantGrpcClient.Builder grpcBuilder = QdrantGrpcClient.newBuilder(channel, true);
        if (qdrant.apiKey() != null && !qdrant.apiKey().isBlank()) {
            grpcBuilder.withApiKey(qdrant.apiKey());
        }
        return new QdrantClient(grpcBuilder.build());
    }
}
