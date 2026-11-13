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
  public DataImportController(DataImportService service){this.service=service;}

  @PostMapping(path="/{type}",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
  public Map<String,Object> upload(@PathVariable String type,@RequestPart("file") MultipartFile file) throws IOException {
    return service.importCsv(type,file.getOriginalFilename(),file.getBytes());
  }

  @ExceptionHandler(ImportRejectedException.class)
  public ResponseEntity<Map<String,Object>> rejected(ImportRejectedException error){
    return ResponseEntity.badRequest().body(Map.of("status","REJECTED","error",error.getMessage()));
  }
}
