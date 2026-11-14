package com.trading;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
@SpringBootApplication @EnableScheduling public class TradingCoreApplication {
 public static void main(String[] args){SpringApplication.run(TradingCoreApplication.class,args);}
}
