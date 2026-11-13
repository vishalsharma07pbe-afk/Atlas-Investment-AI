package com.trading.data;

public class ImportRejectedException extends RuntimeException {
  public ImportRejectedException(String message) { super(message); }
  public ImportRejectedException(String message, Throwable cause) { super(message, cause); }
}
