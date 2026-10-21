package com.example.springdemo;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloController {
    @GetMapping("/")
    public Map<String, String> home() {
        return Map.of("status", "ok", "message", "Spring Boot is running", "java", System.getProperty("java.version"));
    }
}
