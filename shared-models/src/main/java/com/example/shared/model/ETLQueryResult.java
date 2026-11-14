package com.example.shared.model;

import java.util.List;
import java.util.Map;

public class ETLQueryResult {
    private List<Map<String, Object>> chunks;
    
    public ETLQueryResult() {}

    public ETLQueryResult(List<Map<String, Object>> chunks) {
        this.chunks = chunks;
    }

    public List<Map<String, Object>> getChunks() {
        return chunks;
    }

    public void setChunks(List<Map<String, Object>> chunks) {
        this.chunks = chunks;
    }
}
