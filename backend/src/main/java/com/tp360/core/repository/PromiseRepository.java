package com.tp360.core.repository;

import com.tp360.core.domain.Promise;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface PromiseRepository extends JpaRepository<Promise, Long> {
    List<Promise> findByPoliticianId(Long politicianId);
}
