package com.example.coordinator.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.LinkedBlockingQueue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.example.coordinator.model.UserRequest;
import com.example.shared.model.LLMRequest;
import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;

@Service
public class ProcessingService {

    private final RestTemplate restTemplate;
    private final RequestStorage storage;
    private volatile boolean isLeader;
    private volatile boolean isProcessingThreadRunning = false;

    private final Set<String> llmNodes = ConcurrentHashMap.newKeySet();
    private final Set<String> dbNodes = ConcurrentHashMap.newKeySet();
    // ---- add ETL-node ---
    private final Set<String> etlNodes = ConcurrentHashMap.newKeySet();
    // --- add ETL-node ----

    private final LinkedBlockingQueue<String> requestQueue;
    private final ScheduledExecutorService retryScheduler = Executors.newScheduledThreadPool(1);
    private final ConcurrentHashMap<String, Integer> retryCounts = new ConcurrentHashMap<>();

    public ProcessingService(RestTemplate restTemplate, RequestStorage storage) {
        this.restTemplate = restTemplate;
        this.storage = storage;
        isLeader = false;

        this.requestQueue = new LinkedBlockingQueue<>(100);
    }

    public void setIsLeader(boolean input) {
        this.isLeader = input;
    }

    public boolean getIsLeader() {
        return this.isLeader;
    }

    public boolean isProcessingThreadRunning() {
        return this.isProcessingThreadRunning;
    }

    public List<String> getLlmNodes() {
        return new ArrayList<>(llmNodes);
    }

    public void setLlmNodes(List<String> list) {
        // this.llmNodes.clear();
        this.llmNodes.retainAll(list);
        this.llmNodes.addAll(list);
    }

    public List<String> getDbNodes() {
        return new ArrayList<>(dbNodes);
    }

    public void setDbNodes(List<String> list) {
        // this.dbNodes.clear();
        this.dbNodes.retainAll(list);
        this.dbNodes.addAll(list);
    }

    // ---- add ETL-node ---
    public List<String> getEtlNodes() {
        return new ArrayList<>(etlNodes);
    }

    public void setEtlNodes(List<String> list) {
        if (list == null) return;
        this.etlNodes.retainAll(list);
        this.etlNodes.addAll(list);
    }
    // --- add ETL-node ----

    public boolean apply(String id, String type) {
        if (type.equals("llm")) {
            llmNodes.add(id);
        } else if (type.equals("db")) {
            dbNodes.add(id);
        // ---- add ETL-node ---
        } else if (type.equals("etl")) {
            etlNodes.add(id);
        // --- add ETL-node ----
        }
        return true;
    }

    public void updateQueue() { 
        for (String id : storage.getRequestList()) {
            UserRequest req = storage.getRequest(id);
            if (req != null && !req.getState().equals("done") && !req.getState().equals("error")) {
                requestQueue.offer(id);
            }
        }
    } 

    public boolean addToQueue(String id) {
         try {
            requestQueue.put(id);
            return true;
        } catch (Exception e) {return false;}
    }

    public void processingThread() {
        if (isProcessingThreadRunning) return;
        isProcessingThreadRunning = true;
        // add time out??
        Thread checkingThread = new Thread(() -> {
            try {
                while (isLeader) { 
                    try {
                    String id = requestQueue.poll(1, TimeUnit.SECONDS);
                    if (id == null) continue;
                    
                    UserRequest request = storage.getRequest(id);
                    if (request == null) {
                        System.out.println("Request " + id + " was removed (e.g. TTL expired). Skipping.");
                        continue;
                    }

                    if (request.getState().equals("received")) {
                        // ---- add ETL-node ---
                        if ("INGEST".equals(request.getType())) {
                            processIngestJob(id, request);
                            continue;
                        }
                        // --- add ETL-node ----

                        LLMRequest llmRequest = new LLMRequest();
                        llmRequest.setUserQuery(request.getUserQuery());
                        RecipeQuery result = null;
                        try {
                            result = sendToLLMNode(llmRequest);
                        } catch (RuntimeException e) {
                            if ("QUOTA_EXCEEDED".equals(e.getMessage())) {
                                System.out.println("Quota exceeded. Failing fast.");
                                request.setState("quota_exceeded");
                                storage.storeRequest(id, request);
                                storage.broadCastCopy(request);
                                retryCounts.remove(id);
                                continue;
                            }
                        }

                        if (result != null) {
                            request.setState("formatted");
                            request.setRecipeQuery(result);
                            storage.storeRequest(id, request);
                            this.addToQueue(id);
                            storage.broadCastCopy(request);
                        } else {
                            int retries = retryCounts.getOrDefault(id, 0) + 1;
                            if (retries > 3) {
                                System.out.println("LLM decompose permanently failed for " + id);
                                request.setState("error");
                                storage.storeRequest(id, request);
                                storage.broadCastCopy(request);
                                retryCounts.remove(id);
                            } else {
                                retryCounts.put(id, retries);
                                System.out.println("LLM decompose failed for " + id + ". Retrying in 5s... (attempt " + retries + ")");
                                retryScheduler.schedule(() -> this.addToQueue(id), 5, TimeUnit.SECONDS);
                            }
                        }

                    } else if (request.getState().equals("formatted")) {
                        RecipeQuery recipeQuery = request.getRecipeQuery();
                        List<RecipeQueryResult> result = sendToDBNode(recipeQuery);

                        // if (result != null) {
                        //     request.setState("unformatted results");
                        //     request.setRecipeQueryResults(result);
                        //     storage.storeRequest(id, request);
                        //     this.addToQueue(id);
                        //     storage.broadCastCopy(request);
                        // } else {
                        //     System.out.println("No result, request failed.");
                        //     //storage.deleteRequest(id);
                        // }
                        // 
                        // request.setState("unformatted result");
                        // storage.storeRequest(id, request);
                        // this.addToQueue(id);
                        // storage.broadCastCopy(request);
                        // 
                        // } else if (request.getState().equals("unformatted result")) {
                        if (result != null && !result.isEmpty()) {
                            request.setState("searched");
                            request.setRecipeQueryResults(result);
                            storage.storeRequest(id, request);
                            this.addToQueue(id);
                            storage.broadCastCopy(request);
                        } else {
                            int retries = retryCounts.getOrDefault(id, 0) + 1;
                            if (retries > 3) {
                                System.out.println("Recipe DB search permanently failed for " + id);
                                request.setState("error");
                                storage.storeRequest(id, request);
                                storage.broadCastCopy(request);
                                retryCounts.remove(id);
                            } else {
                                retryCounts.put(id, retries);
                                System.out.println("Recipe DB search failed for " + id + " (result=" + (result == null ? "null" : "empty") + "). Retrying in 5s... (attempt " + retries + ")");
                                retryScheduler.schedule(() -> this.addToQueue(id), 5, TimeUnit.SECONDS);
                            }
                        }

                    } else if (request.getState().equals("searched")) {


                        String finalResult = null;
                        try {
                            finalResult = sendToLLMAnswerNode(request);
                        } catch (RuntimeException e) {
                            if ("QUOTA_EXCEEDED".equals(e.getMessage())) {
                                System.out.println("Quota exceeded. Failing fast.");
                                request.setState("quota_exceeded");
                                storage.storeRequest(id, request);
                                storage.broadCastCopy(request);
                                retryCounts.remove(id);
                                continue;
                            }
                        }
                        if (finalResult != null) {
                            request.setState("done");
                            try {
                                ObjectMapper mapper = new ObjectMapper();
                                JsonNode root = mapper.readTree(finalResult);
                                if (root.has("answer")) {
                                    request.setResult(root.get("answer").asText());
                                } else {
                                    request.setResult(finalResult);
                                }
                            } catch (Exception e) {
                                request.setResult(finalResult);
                            }
                            storage.storeRequest(id, request);
                            storage.broadCastCopy(request);
                        } else {
                            int retries = retryCounts.getOrDefault(id, 0) + 1;
                            if (retries > 3) {
                                System.out.println("LLM answer generation permanently failed for " + id);
                                request.setState("error");
                                storage.storeRequest(id, request);
                                storage.broadCastCopy(request);
                                retryCounts.remove(id);
                            } else {
                                retryCounts.put(id, retries);
                                System.out.println("LLM answer generation failed for " + id + ". Retrying in 5s... (attempt " + retries + ")");
                                retryScheduler.schedule(() -> this.addToQueue(id), 5, TimeUnit.SECONDS);
                            }
                        }
                        
                    } else {
                        System.out.println("Something went very wrong");
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    System.err.println("The sleep was interrupted.");
                } catch (Exception e) {
                    System.out.println("The node cannot be called");
                    e.printStackTrace();
                }
            }
            } finally {
                isProcessingThreadRunning = false;
            }
        });

        checkingThread.setDaemon(true); 
        checkingThread.start();
    }

    // ---- add ETL-node ---
    private void processIngestJob(String id, UserRequest request) {
        if ("received".equals(request.getState())) {
            try {
                com.example.shared.model.ETLQuery.Dish sharedDish = request.getIngestDish();
                if (sharedDish == null) {
                    System.out.println("No dish payload found for ingest job " + id);
                    request.setState("error");
                    storage.storeRequest(id, request);
                    return;
                }

                // ---- add ETL-node ---
                List<String> etlNodeList = new ArrayList<>(this.etlNodes);
                if (etlNodeList.isEmpty()) {
                    retryOrFail(id, request, "ETL node unavailable");
                    return;
                }
                
                String node = etlNodeList.get(ThreadLocalRandom.current().nextInt(etlNodeList.size()));
                String targetUrl = formatUrl(node, "/etl/process");
                
                com.example.shared.model.ETLQuery etlQuery = new com.example.shared.model.ETLQuery();
                etlQuery.setDishes(List.of(sharedDish));

                com.example.shared.model.ETLQueryResult result = restTemplate.postForObject(targetUrl, etlQuery, com.example.shared.model.ETLQueryResult.class);
                
                if (result == null || result.getChunks() == null) {
                    retryOrFail(id, request, "ETL processing returned null");
                    return;
                }

                List<String> dbNodeList = new ArrayList<>(this.dbNodes);
                if (dbNodeList.isEmpty()) {
                    retryOrFail(id, request, "DB node unavailable");
                    return;
                }
                
                String dbNode = dbNodeList.get(ThreadLocalRandom.current().nextInt(dbNodeList.size()));
                String dbTargetUrl = formatUrl(dbNode, "/recipes/ingest");
                
                String response = restTemplate.postForObject(dbTargetUrl, result, String.class);
                System.out.println("Recipe Node saved dish successfully. Response: " + response);
                
                request.setState("done");
                storage.storeRequest(id, request);
                storage.broadCastCopy(request);
                // --- add ETL-node ----
            } catch (Exception e) {
                System.err.println("Failed to process dish ingest: " + e.getMessage());
                retryOrFail(id, request, e.getMessage());
            }
        }
    }

    private void retryOrFail(String id, UserRequest request, String errorMsg) {
        int retries = retryCounts.getOrDefault(id, 0) + 1;
        if (retries > 3) {
            System.out.println("Ingest job permanently failed for " + id + ": " + errorMsg);
            request.setState("error");
            storage.storeRequest(id, request);
            retryCounts.remove(id);
        } else {
            retryCounts.put(id, retries);
            System.out.println("Ingest job failed for " + id + ". Retrying in 5s... (attempt " + retries + ")");
            retryScheduler.schedule(() -> this.addToQueue(id), 5, TimeUnit.SECONDS);
        }
    }
    // --- add ETL-node ----

    private RecipeQuery sendToLLMNode(LLMRequest llmRequest) {
        int numberOfNodes = llmNodes.size();
        if (numberOfNodes > 0)  {
            int attempt = 0;
            do {
                attempt = attempt + 1;
                String node = (String) llmNodes.toArray()[ThreadLocalRandom.current().nextInt(numberOfNodes)];
                try {
                    String targetUrl = formatUrl(node, "/llm/decompose");

                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    HttpEntity<LLMRequest> entity = new HttpEntity<>(llmRequest, headers);

                    return restTemplate.postForObject(targetUrl, entity, RecipeQuery.class);
                } catch (Exception e) {
                    System.out.println("Calling llm service failed: " + e.getMessage());
                    if (e.getMessage() != null && e.getMessage().contains("429")) {
                        throw new RuntimeException("QUOTA_EXCEEDED", e);
                    }
                    e.printStackTrace();
                }
            } while (attempt < 2);
            return null;
        } else {
            System.out.println("No llm nodes found");
            return null;
        }
    }
    
    private List<RecipeQueryResult> sendToDBNode(RecipeQuery recipeQuery) {
        int numberOfNodes = dbNodes.size();
        List<RecipeQueryResult> results = new ArrayList<>();
        if (numberOfNodes > 0)  {
            int attempt = 0;
            do {
                attempt++;
                String node = (String) dbNodes.toArray()[ThreadLocalRandom.current().nextInt(numberOfNodes)];
                try {
                    String targetUrl = formatUrl(node, "/recipes/search");
                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    HttpEntity<RecipeQuery> entity = new HttpEntity<>(recipeQuery, headers);

                    ResponseEntity<List<RecipeQueryResult>> response = restTemplate.exchange(
                            targetUrl, HttpMethod.POST, entity,
                            new ParameterizedTypeReference<List<RecipeQueryResult>>() {}
                    );

                    if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                        results.addAll(response.getBody());
                        break; // Exit the loop on success
                    }
                } catch (Exception e) {
                    System.out.println("Calling RECIPE NODE service failed: " + node);
                    e.printStackTrace();
                }
            } while (attempt < 3);

            return results;
        } else {
            System.out.println("No db nodes found");
            return null;
        }
    }

    private String sendToLLMAnswerNode(UserRequest userRequest) {
        int numberOfNodes = llmNodes.size();
        if (numberOfNodes > 0)  {
            int attempt = 0;
            do {
                attempt = attempt + 1;
                String node = (String) llmNodes.toArray()[ThreadLocalRandom.current().nextInt(numberOfNodes)];
                try {
                    String targetUrl = formatUrl(node, "/llm/answer");
                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    HttpEntity<UserRequest> entity = new HttpEntity<>(userRequest, headers);

                    return restTemplate.postForObject(targetUrl, entity, String.class);
                } catch (Exception e) {
                    System.out.println("Calling llm service failed: " + e.getMessage());
                    if (e.getMessage() != null && e.getMessage().contains("429")) {
                        throw new RuntimeException("QUOTA_EXCEEDED", e);
                    }
                    e.printStackTrace();
                }
            } while (attempt < 2);
            return null;
        } else {
            System.out.println("No llm nodes found");
            return null;
        }
    }

    private String formatUrl(String idOrAddress, String path) {
        if (idOrAddress.contains(":") || idOrAddress.contains(".") || idOrAddress.equalsIgnoreCase("localhost")) {
            return "http://" + idOrAddress + path;
        }
        return "http://localhost:" + idOrAddress + path;
    }
}