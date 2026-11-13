package com.trading.data;

import java.nio.charset.StandardCharsets;
import java.util.*;

final class CsvTable {
  private CsvTable() {}

  static List<Map<String,String>> parse(byte[] bytes, List<String> expected) {
    if (bytes.length == 0) throw new ImportRejectedException("CSV file is empty");
    if (bytes.length > 10 * 1024 * 1024) throw new ImportRejectedException("CSV exceeds the 10 MB limit");
    String text = new String(bytes, StandardCharsets.UTF_8).replace("\r\n", "\n").replace('\r', '\n');
    if (text.startsWith("\uFEFF")) text = text.substring(1);
    String[] lines = text.split("\n", -1);
    if (lines.length < 2) throw new ImportRejectedException("CSV must contain a header and at least one data row");
    List<String> header = split(lines[0], 1);
    if (!header.equals(expected)) throw new ImportRejectedException("CSV headers must be exactly: " + String.join(",", expected));
    List<Map<String,String>> rows = new ArrayList<>();
    for (int line = 1; line < lines.length; line++) {
      if (lines[line].isBlank()) continue;
      List<String> values = split(lines[line], line + 1);
      if (values.size() != header.size()) throw new ImportRejectedException("Line " + (line + 1) + " has " + values.size() + " columns; expected " + header.size());
      Map<String,String> row = new LinkedHashMap<>();
      for (int i = 0; i < header.size(); i++) row.put(header.get(i), values.get(i).trim());
      row.put("_line", Integer.toString(line + 1));
      rows.add(row);
    }
    if (rows.isEmpty()) throw new ImportRejectedException("CSV has no data rows");
    return rows;
  }

  private static List<String> split(String line, int number) {
    if (line.indexOf('"') >= 0) throw new ImportRejectedException("Line " + number + " contains quotes; this strict adapter accepts only unquoted fields without embedded commas");
    return Arrays.stream(line.split(",", -1)).map(String::trim).toList();
  }
}
