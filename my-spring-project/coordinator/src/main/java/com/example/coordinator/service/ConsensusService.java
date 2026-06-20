package com.example.coordinator.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import com.example.coordinator.model.NodesInfo;
import com.example.coordinator.model.VoteRequest;

@Component 
public class ConsensusService {
    private final RestTemplate restTemplate;
    private final ProcessingService processingService;
    private final RequestStorage storage;

    private final Set<String> nodesList = ConcurrentHashMap.newKeySet();
    @Value("${node.id:${server.port:8080}}")
    private String nodeId;
    
    private volatile String nodeStatus; 
    private volatile String leaderId; 

    private final AtomicInteger term;
    private final AtomicBoolean voted;
    private final AtomicBoolean leaderAlive;

    public ConsensusService(RestTemplate restTemplate, 
            ProcessingService processingService, RequestStorage storage) {
        this.restTemplate = restTemplate;
        this.processingService = processingService;
        this.storage = storage;

        this.nodeStatus = "follower";
        this.leaderId = null;
        
        this.term = new AtomicInteger(0);
        this.voted = new AtomicBoolean(false);
        this.leaderAlive = new AtomicBoolean(false);
        }

    /**
     * Handles incoming vote requests from candidates.
     * Grants vote if the candidate's term is greater or equal and it has sufficient requests.
     */
    public boolean vote(VoteRequest request) { 
        int requestCount = storage.getRequestList().size();

        if (this.term.get() <= request.getTerm() && requestCount <= request.getRequestCount()) {
            if(this.term.get() < request.getTerm()) {
                this.term.set(request.getTerm());
                this.voted.set(false);
            }
            int candidateRequestCount = request.getRequestCount();
            
            if (candidateRequestCount >= requestCount && this.voted.compareAndSet(false, true)) {
                return true;
            } 
        }
        return false;
    }

    /**
     * Receives heartbeats from the Leader.
     * Resets the election timeout and updates the current term.
     */
    public boolean ping(String id, int term) {
        if (term >= this.term.get()) {
            this.leaderId = id;
            this.leaderAlive.set(true);
            this.nodeStatus = "follower";
            processingService.setIsLeader(false);
            this.term.set(term);
            return true;
        } else {return false;}
    }

    /**
     * Registers a new node to the cluster.
     * If this node is the leader, it broadcasts the new node to all followers.
     */
    public NodesInfo join(String id) {
        if (nodeStatus.equals("leader")) {
            Boolean validity = false;
            try {
                String targetUrl = formatUrl(id, "/ping");
                String urlTemplate = UriComponentsBuilder.fromHttpUrl(targetUrl)
                        .queryParam("id", nodeId)
                        .queryParam("term", this.term.get())
                        .encode()
                        .toUriString();

                validity = restTemplate.postForObject(urlTemplate, null, Boolean.class);
            } catch (RestClientException e) { System.out.println("Ping failed.");}

            if (Boolean.TRUE.equals(validity)) {
                nodesList.add(id);
                storage.addNode(id);

                for (String node : nodesList) {
                    try {
                        String targetUrl = formatUrl(node, "/join");
                        String urlTemplate = UriComponentsBuilder.fromHttpUrl(targetUrl)
                                .queryParam("id", id)
                                .encode()
                                .toUriString();
                        restTemplate.postForObject(urlTemplate, null, Boolean.class);
                    } catch (RestClientException e) { System.out.println("Ping failed.");}
                }

                List<String> coordinators = new ArrayList<>(nodesList);
                coordinators.add(nodeId);
                coordinators.remove(id);

                NodesInfo info = new NodesInfo();
                info.setCoordinatorNodes(coordinators);
                info.setLlmNodes(processingService.getLlmNodes());
                info.setRecipeNodes(processingService.getDbNodes());
                // ---- add ETL-node ---
                info.setEtlNodes(processingService.getEtlNodes());
                // --- add ETL-node ----
                return info;
            }
            return null;
        
        } else {
            nodesList.add(id);
            storage.addNode(id);
        }
        return null;
    }

    /**
     * Forces this node to follow a new leader.
     */
    public boolean follow(String id) {
        if (id.equals(nodeId)) {return false;}
        try {
            String targetUrl = formatUrl(id, "/join");
            String urlTemplate = UriComponentsBuilder.fromHttpUrl(targetUrl)
                    .queryParam("id", nodeId)
                    .encode()
                    .toUriString();
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Void> entity = new HttpEntity<>(headers);
            NodesInfo info = restTemplate.postForObject(urlTemplate, entity, NodesInfo.class);
            
            if (info == null) {
                return false;
            } else {
                nodesList.clear();
                nodesList.addAll(info.getCoordinatorNodes());
                storage.setNode(info.getCoordinatorNodes());
                processingService.setLlmNodes(info.getLlmNodes());
                processingService.setDbNodes(info.getRecipeNodes());
                // ---- add ETL-node ---
                processingService.setEtlNodes(info.getEtlNodes());
                // --- add ETL-node ----
                return true;
            }
        } catch (Exception e) {
            System.out.println("Following nodes failed.");
            return false;
        }
    }

    public boolean apply(String id, String type) {
        if (nodeStatus.equals("leader")) {
            // Later: try service first, to prevent fraud
            processingService.apply(id, type);
            for (String node : nodesList) {
                try {
                String targetUrl = formatUrl(node, "/apply");
                String urlTemplate = UriComponentsBuilder.fromHttpUrl(targetUrl)
                        .queryParam("id", id)
                        .queryParam("type", type)
                        .encode()
                        .toUriString();
                restTemplate.postForObject(urlTemplate, null, Boolean.class);
                } catch (RestClientException e) { System.out.println("Broadcasting new worker nodes failed.");}
            }
            return true;
        } else {
            processingService.apply(id, type);
        }
        return false;
    }

    public String redirect(com.example.shared.model.LLMRequest request) {
        System.out.println("Redirecting..");
        if (leaderId != null) {
            try {
                String targetUrl = formatUrl(leaderId, "/search");
                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.APPLICATION_JSON);
                HttpEntity<com.example.shared.model.LLMRequest> entity = new HttpEntity<>(request, headers);
                return restTemplate.postForObject(targetUrl, entity, String.class);
            } catch (Exception e) {
                System.out.println("Redirecting fails: " + e.getMessage());
            }
        }
        return null;
    }

    public com.example.coordinator.controller.DishController.Dish redirectIngest(com.example.coordinator.controller.DishController.Dish request, String authHeader) {
        System.out.println("Redirecting ingest to leader: " + leaderId);
        if (leaderId != null) {
            try {
                String targetUrl = formatUrl(leaderId, "/api/dishes");
                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.APPLICATION_JSON);
                if (authHeader != null) {
                    headers.set("Authorization", authHeader);
                }
                HttpEntity<com.example.coordinator.controller.DishController.Dish> entity = new HttpEntity<>(request, headers);
                return restTemplate.postForObject(targetUrl, entity, com.example.coordinator.controller.DishController.Dish.class);
            } catch (Exception e) {
                System.out.println("Redirecting ingest fails: " + e.getMessage());
                throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE, "Redirect failed: " + e.getMessage());
            }
        }
        throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE, "No leader available to redirect to.");
    }

    /**
     * Leader continuously pings followers to maintain authority.
     * Steps down to follower if a ping fails significantly (split brain prevention).
     */
    @Scheduled(fixedDelay = 1000)
    public void pingingThread() {
        if (nodeStatus.equals("leader")) {
            for (String node : nodesList) {
                try {
                    String targetUrl = formatUrl(node, "/ping");
                    String urlTemplate = UriComponentsBuilder.fromHttpUrl(targetUrl)
                            .queryParam("id", nodeId)
                            .queryParam("term", this.term.get())
                            .encode()
                            .toUriString();

                    Boolean response = restTemplate.postForObject(urlTemplate, null, Boolean.class);
                    if (response == null || !response) {
                        nodeStatus = "follower"; 
                        processingService.setIsLeader(false);
                        }
                    // Later: only step down if less than 1/2 success ping.
                } catch (Exception e) {System.out.println("Broadcast failed.");}
            }
            System.out.println("Pinging other nodes.");
        }
    }

    /**
     * Follower timeout checker. If no heartbeat is received from the leader
     * within the threshold, this node becomes a candidate and starts an election.
     */
    @Scheduled(fixedDelay = 5000)
    public void scheduledTask() {
        System.out.println("Current Status: " + this.nodeStatus + " " + this.term.get());

        if (this.nodeStatus.equals("follower")) {
            if (!this.leaderAlive.compareAndSet(true, false)) {
                this.nodeStatus = "candidate";
                this.leaderId = null;
                processingService.setIsLeader(false);
                new Thread(this::runElection).start();
            }
        }
    }

    /**
     * Executes the Raft leader election process.
     * Requests votes from all known nodes and becomes Leader if the majority grants the vote.
     */
    private void runElection() {
        while (this.nodeStatus.equals("candidate")) {
            try {
                long randomDelay = ThreadLocalRandom.current().nextLong(1000, 2000 + 1);
                Thread.sleep(randomDelay);
            } catch (InterruptedException ignore) {}

            if (!this.nodeStatus.equals("candidate")) return;

            this.term.incrementAndGet();
            this.voted.set(false);
            int vote = 1;

            VoteRequest request = new VoteRequest();
            request.setRequestCount(storage.getRequestList().size());
            request.setCandidateId(this.nodeId);
            request.setTerm(this.term.get());

            System.out.println("Start election " + this.term.get());

            // check status again maybe??
            for (String node : nodesList) {
                try {
                    String targetUrl = formatUrl(node, "/vote");
                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    HttpEntity<VoteRequest> entity = new HttpEntity<>(request, headers);
                    Boolean result = restTemplate.postForObject(targetUrl, entity, Boolean.class);
                    if (Boolean.TRUE.equals(result)) {vote = vote + 1;}
                } catch (RestClientException e) { System.out.println("Ask for vote failed.");}
            }

            if (vote > ((nodesList.size() + 1) / 2) && this.nodeStatus.equals("candidate")) {
                this.nodeStatus = "leader";
                this.leaderId = null;
                processingService.setIsLeader(true);
                processingService.processingThread(); 
                processingService.updateQueue();
                System.out.println("Won");
            }
            else {System.out.println("Lost");}
        }
    }

    private String formatUrl(String idOrAddress, String path) {
        if (idOrAddress.contains(":") || idOrAddress.contains(".") || idOrAddress.equalsIgnoreCase("localhost")) {
            return "http://" + idOrAddress + path;
        }
        return "http://localhost:" + idOrAddress + path;
    }
}