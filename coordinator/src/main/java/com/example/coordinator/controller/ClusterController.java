package com.example.coordinator.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.coordinator.model.NodesInfo;
import com.example.coordinator.model.UserRequest;
import com.example.coordinator.model.VoteRequest;
import com.example.coordinator.service.ConsensusService;
import com.example.coordinator.service.RequestStorage;

@RestController
@RequestMapping("/")
public class ClusterController {

    private final ConsensusService consensus;
    private final RequestStorage storage;

    public ClusterController(ConsensusService consensus, RequestStorage storage) {
        this.consensus = consensus;
        this.storage = storage;
    }

    @PostMapping("/copy") 
    public boolean copy(@RequestBody UserRequest request) { 
        storage.storeRequest(request.getId(), request);
        return true;
    }

    @PostMapping("/ping") 
    public boolean ping(@RequestParam String id, @RequestParam int term) { 
        return consensus.ping(id, term);
    }

    @PostMapping("/vote") 
    public boolean vote(@RequestBody VoteRequest request) { 
        return consensus.vote(request);
    }

    @PostMapping("/join") 
    public NodesInfo join(@RequestParam String id) { 
        return consensus.join(id);
    }

    @PostMapping("/apply") 
    public boolean apply(@RequestParam String id, @RequestParam String type) { 
        return consensus.apply(id, type);
    }

    @PostMapping("/follow") 
    public boolean follow(@RequestParam String id) { 
        return consensus.follow(id);
    }
}
