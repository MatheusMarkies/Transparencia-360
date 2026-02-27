package com.tp360.core.controller;

import com.tp360.core.domain.Politician;
import com.tp360.core.repository.PoliticianRepository;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Collections;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.anyString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(FrontendSearchController.class)
public class FrontendSearchControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private PoliticianRepository politicianRepository;

    @Test
    public void shouldReturnPoliticiansListOnSearch() throws Exception {
        Politician p = new Politician();
        p.setId(1L);
        p.setName("João Teste");
        p.setParty("TESTE");
        p.setState("SP");
        
        Mockito.when(politicianRepository.findByNameContainingIgnoreCase(anyString()))
               .thenReturn(Collections.singletonList(p));

        mockMvc.perform(get("/api/v1/politicians/search?name=joao"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$[0].name").value("João Teste"))
               .andExpect(jsonPath("$[0].party").value("TESTE"));
    }

    @Test
    public void shouldReturnPoliticianDetailsOnGetById() throws Exception {
        Politician p = new Politician();
        p.setId(1L);
        p.setName("João Teste");
        
        Mockito.when(politicianRepository.findById(1L))
               .thenReturn(Optional.of(p));

        mockMvc.perform(get("/api/v1/politicians/1"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.name").value("João Teste"));
    }
}
