package com.tp360.core.repository;

import com.tp360.core.domain.Politician;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface PoliticianRepository extends JpaRepository<Politician, Long> {
    Optional<Politician> findByExternalId(String externalId);
}
