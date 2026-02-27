package com.tp360.core.service;

import com.tp360.core.domain.Politician;
import com.tp360.core.domain.Promise;
import com.tp360.core.domain.Vote;
import com.tp360.core.repository.PoliticianRepository;
import com.tp360.core.repository.PromiseRepository;
import com.tp360.core.repository.VoteRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
public class DataIngestionService {

    private final PoliticianRepository politicianRepository;
    private final PromiseRepository promiseRepository;
    private final VoteRepository voteRepository;

    public DataIngestionService(PoliticianRepository politicianRepository,
                                PromiseRepository promiseRepository,
                                VoteRepository voteRepository) {
        this.politicianRepository = politicianRepository;
        this.promiseRepository = promiseRepository;
        this.voteRepository = voteRepository;
    }

    @Transactional
    public Politician ingestPolitician(Politician data) {
        Optional<Politician> existing = politicianRepository.findByExternalId(data.getExternalId());
        if (existing.isPresent()) {
            Politician p = existing.get();
            p.setName(data.getName());
            p.setParty(data.getParty());
            p.setState(data.getState());
            p.setPosition(data.getPosition());
            return politicianRepository.save(p);
        }
        return politicianRepository.save(data);
    }

    @Transactional
    public Promise ingestPromise(String externalPoliticianId, Promise promise) {
        Politician p = politicianRepository.findByExternalId(externalPoliticianId)
                .orElseThrow(() -> new IllegalArgumentException("Politician not found"));
        promise.setPolitician(p);
        return promiseRepository.save(promise);
    }

    @Transactional
    public Vote ingestVote(String externalPoliticianId, Vote vote) {
        Politician p = politicianRepository.findByExternalId(externalPoliticianId)
                .orElseThrow(() -> new IllegalArgumentException("Politician not found"));
        vote.setPolitician(p);
        
        Optional<Vote> existing = voteRepository.findByPoliticianIdAndPropositionExternalId(
                p.getId(), vote.getPropositionExternalId());
        
        if (existing.isPresent()) {
            Vote v = existing.get();
            v.setVoteChoice(vote.getVoteChoice());
            return voteRepository.save(v);
        }
        
        return voteRepository.save(vote);
    }
}
