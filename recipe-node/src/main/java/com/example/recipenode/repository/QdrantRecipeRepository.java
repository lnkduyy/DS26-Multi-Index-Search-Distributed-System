package com.example.recipenode.repository;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Repository;

import com.example.recipenode.config.RecipeNodeProperties;
import com.example.recipenode.model.RecipeCandidate;

import io.qdrant.client.QdrantClient;
import static io.qdrant.client.QueryFactory.nearest;
import static io.qdrant.client.WithPayloadSelectorFactory.enable;
import io.qdrant.client.grpc.JsonWithInt;
import io.qdrant.client.grpc.Points.Document;
import io.qdrant.client.grpc.Points.QueryPoints;
import io.qdrant.client.grpc.Points.ScoredPoint;

@Repository
public class QdrantRecipeRepository {
    private static final Logger log = LoggerFactory.getLogger(QdrantRecipeRepository.class);

    private final QdrantClient qdrantClient;
    private final RecipeNodeProperties properties;

    public QdrantRecipeRepository(
            QdrantClient qdrantClient,
            RecipeNodeProperties properties
    ) {
        this.qdrantClient = qdrantClient;
        this.properties = properties;
    }

    public List<RecipeCandidate> findCandidates(String semanticText) {
        if (semanticText == null || semanticText.isBlank()) {
            return List.of();
        }

        RecipeNodeProperties.Qdrant qdrant = properties.qdrant();
        QueryPoints.Builder request = QueryPoints.newBuilder()
                .setCollectionName(qdrant.collection())
                .setQuery(nearest(Document.newBuilder()
                        .setText(semanticText)
                        .setModel(qdrant.inferenceModel())
                        .build()))
                .setLimit(properties.candidateLimit())
                .setWithPayload(enable(true));

        if (qdrant.vectorName() != null && !qdrant.vectorName().isBlank()) {
            request.setUsing(qdrant.vectorName());
        }

        try {
            List<ScoredPoint> points = qdrantClient.queryAsync(request.build()).get(properties.queryTimeoutSeconds(), TimeUnit.SECONDS);
            List<RecipeCandidate> candidates = new ArrayList<>(points.size());
            for (ScoredPoint point : points) {
                candidates.add(new RecipeCandidate(
                        point.getId().hasUuid() ? point.getId().getUuid() : String.valueOf(point.getId().getNum()),
                        point.getScore(),
                        convertPayload(point.getPayloadMap())
                ));
            }
            return candidates;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RecipeRepositoryException("Interrupted while querying Qdrant recipes collection", e);
        } catch (ExecutionException | TimeoutException e) {
            log.warn("Qdrant recipe search failed or timed out for collection {}", qdrant.collection(), e);
            throw new RecipeRepositoryException("Unable to query Qdrant recipes collection", e);
        }
    }

    private Map<String, Object> convertPayload(Map<String, JsonWithInt.Value> payload) {
        Map<String, Object> converted = new LinkedHashMap<>();
        for (Map.Entry<String, JsonWithInt.Value> entry : payload.entrySet()) {
            converted.put(entry.getKey(), convertValue(entry.getValue()));
        }
        return converted;
    }

    private Object convertValue(JsonWithInt.Value value) {
        if (value == null) {
            return null;
        }
        return switch (value.getKindCase()) {
            case NULL_VALUE, KIND_NOT_SET -> null;
            case DOUBLE_VALUE -> value.getDoubleValue();
            case INTEGER_VALUE -> value.getIntegerValue();
            case STRING_VALUE -> value.getStringValue();
            case BOOL_VALUE -> value.getBoolValue();
            case STRUCT_VALUE -> convertPayload(value.getStructValue().getFieldsMap());
            case LIST_VALUE -> value.getListValue().getValuesList().stream()
                    .map(this::convertValue)
                    .toList();
        };
    }

    // ---- add ETL-node ---
    public void upsertChunks(List<Map<String, Object>> chunks) {
        RecipeNodeProperties.Qdrant qdrant = properties.qdrant();
        List<io.qdrant.client.grpc.Points.PointStruct> points = new ArrayList<>();
        
        for (Map<String, Object> chunk : chunks) {
            String idStr = java.util.UUID.randomUUID().toString();
            Map<String, Object> metadata = (Map<String, Object>) chunk.get("metadata");
            if (chunk.containsKey("id") && chunk.get("id") != null) {
                idStr = chunk.get("id").toString();
            } else if (metadata != null && metadata.containsKey("id")) {
                idStr = metadata.get("id").toString();
            }
            
            List<Double> vectorList = (List<Double>) chunk.get("vector");
            if (vectorList == null) {
                log.warn("Missing vector in chunk for id: {}", idStr);
                continue;
            }
            List<Float> floatList = new ArrayList<>(vectorList.size());
            for (Double v : vectorList) floatList.add(v.floatValue());
            
            Map<String, io.qdrant.client.grpc.JsonWithInt.Value> payload = new LinkedHashMap<>();
            if (metadata != null) {
                for (Map.Entry<String, Object> entry : metadata.entrySet()) {
                    io.qdrant.client.grpc.JsonWithInt.Value v = mapValue(entry.getValue());
                    if (v != null) {
                        payload.put(entry.getKey(), v);
                    }
                }
            }
            payload.put("text", io.qdrant.client.ValueFactory.value((String) chunk.get("text")));
            
            points.add(io.qdrant.client.grpc.Points.PointStruct.newBuilder()
                    .setId(io.qdrant.client.PointIdFactory.id(java.util.UUID.fromString(idStr)))
                    .setVectors(io.qdrant.client.grpc.Points.Vectors.newBuilder().setVector(
                        io.qdrant.client.grpc.Points.Vector.newBuilder().addAllData(floatList).build()
                    ).build())
                    .putAllPayload(payload)
                    .build());
        }
        
        if (!points.isEmpty()) {
            try {
                qdrantClient.upsertAsync(qdrant.collection(), points).get(10, TimeUnit.SECONDS);
                log.info("Upserted {} chunks to Qdrant collection {}", points.size(), qdrant.collection());
            } catch (Exception e) {
                log.error("Failed to upsert chunks to Qdrant", e);
            }
        }
    }

    private io.qdrant.client.grpc.JsonWithInt.Value mapValue(Object obj) {
        if (obj == null) return io.qdrant.client.ValueFactory.nullValue();
        if (obj instanceof String s) return io.qdrant.client.ValueFactory.value(s);
        if (obj instanceof Integer i) return io.qdrant.client.ValueFactory.value((long) i);
        if (obj instanceof Long l) return io.qdrant.client.ValueFactory.value(l);
        if (obj instanceof Float f) return io.qdrant.client.ValueFactory.value((double) f);
        if (obj instanceof Double d) return io.qdrant.client.ValueFactory.value(d);
        if (obj instanceof Boolean b) return io.qdrant.client.ValueFactory.value(b);
        if (obj instanceof List<?> l) {
            List<io.qdrant.client.grpc.JsonWithInt.Value> list = new ArrayList<>();
            for (Object item : l) {
                io.qdrant.client.grpc.JsonWithInt.Value v = mapValue(item);
                if (v != null) list.add(v);
            }
            return io.qdrant.client.ValueFactory.value(list);
        }
        if (obj instanceof Map<?, ?> m) {
            Map<String, io.qdrant.client.grpc.JsonWithInt.Value> map = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : m.entrySet()) {
                io.qdrant.client.grpc.JsonWithInt.Value v = mapValue(entry.getValue());
                if (v != null) map.put(entry.getKey().toString(), v);
            }
            return io.qdrant.client.ValueFactory.value(map);
        }
        return io.qdrant.client.ValueFactory.value(obj.toString());
    }
    // --- add ETL-node ----
}
