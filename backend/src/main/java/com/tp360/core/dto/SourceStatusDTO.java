package com.tp360.core.dto;

public class SourceStatusDTO {
    private String name;
    private String url;
    private String status;
    private String icon;
    private Integer found;
    private String detail;

    public SourceStatusDTO(String name, String url, String status, String icon, Integer found, String detail) {
        this.name = name;
        this.url = url;
        this.status = status;
        this.icon = icon;
        this.found = found;
        this.detail = detail;
    }

    // Getters and Setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getIcon() { return icon; }
    public void setIcon(String icon) { this.icon = icon; }
    public Integer getFound() { return found; }
    public void setFound(Integer found) { this.found = found; }
    public String getDetail() { return detail; }
    public void setDetail(String detail) { this.detail = detail; }
}
