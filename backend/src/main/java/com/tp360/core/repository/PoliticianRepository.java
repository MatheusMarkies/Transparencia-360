package com.tp360.core.repository;

import com.tp360.core.domain.Politician;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PoliticianRepository extends JpaRepository<Politician, Long> {
    Optional<Politician> findByExternalId(String externalId);

    // For deduplication: find first exact name match
    Optional<Politician> findFirstByNameIgnoreCase(String name);

    List<Politician> findByNameContainingIgnoreCase(String name);
}
