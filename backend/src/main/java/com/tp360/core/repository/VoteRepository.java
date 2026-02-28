package com.tp360.core.repository;

import com.tp360.core.domain.Vote;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface VoteRepository extends JpaRepository<Vote, Long> {
    List<Vote> findByPoliticianId(Long politicianId);
    Optional<Vote> findByPoliticianIdAndPropositionExternalId(Long politicianId, String propositionExternalId);
}
