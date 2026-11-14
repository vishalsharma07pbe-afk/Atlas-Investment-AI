package com.trading.api;

import com.trading.data.DataImportService;
import com.trading.data.ImportRejectedException;
import java.io.IOException;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/data-import")
public class DataImportController {
  private final DataImportService service;
  private final org.springframework.jdbc.core.JdbcTemplate jdbc;
  public DataImportController(DataImportService service,org.springframework.jdbc.core.JdbcTemplate jdbc){this.service=service;this.jdbc=jdbc;}

  @PostMapping(path="/{type}",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
  public Map<String,Object> upload(@PathVariable String type,@RequestPart("file") MultipartFile file) throws IOException {
    return service.importCsv(type,file.getOriginalFilename(),file.getBytes());
  }

  @PostMapping(path="/queue/{type}",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
  public Map<String,Object> queue(@PathVariable String type,@RequestParam String exchange,@RequestPart("file") MultipartFile file) throws Exception {
    if(!java.util.Set.of("daily-candles","corporate-actions","market-sessions").contains(type)
      ||!java.util.Set.of("NSE","BSE").contains(exchange))
      throw new ImportRejectedException("Invalid queued job type or exchange");
    byte[] bytes=file.getBytes();
    if(bytes.length==0||bytes.length>5_000_000)throw new ImportRejectedException("Artifact must be 1..5000000 bytes");
    String digest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
    long source=jdbc.queryForObject("SELECT id FROM data_sources WHERE source_code='MANUAL_CSV' AND enabled",Long.class);
    Long id=jdbc.queryForObject("""
      INSERT INTO market_ingestion_queue(source_id,exchange_code,job_type,artifact_name,artifact_sha256,csv_payload)
      VALUES (?,?,?,?,?,?) ON CONFLICT(source_id,job_type,artifact_sha256)
      DO UPDATE SET artifact_name=market_ingestion_queue.artifact_name RETURNING id
      """,Long.class,source,exchange,type,"queued.csv",digest,bytes);
    return Map.of("queueId",id,"status","STAGED");
  }

  @ExceptionHandler(ImportRejectedException.class)
  public ResponseEntity<Map<String,Object>> rejected(ImportRejectedException error){
    return ResponseEntity.badRequest().body(Map.of("status","REJECTED","error",error.getMessage()));
  }
}
