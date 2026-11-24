package com.trading.market;

import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class UserAlertEvaluator {
  private final JdbcTemplate jdbc;
  @Value("${atlas.alerts.scheduler.enabled:true}") boolean enabled;
  public UserAlertEvaluator(JdbcTemplate jdbc){this.jdbc=jdbc;}

  @Scheduled(fixedDelayString="${atlas.alerts.scheduler.poll-ms:60000}")
  public void scheduled(){if(enabled)evaluate();}

  public int evaluate(){
    int delivered=0;
    for(Map<String,Object> rule:jdbc.queryForList("""
      SELECT id,user_id,name,alert_type,target_identifier,
        upper(condition->>'operator') operator,condition->>'value' threshold
      FROM user_alert_rules
      WHERE enabled AND condition ? 'operator' AND condition ? 'value'
        AND condition->>'value' ~ '^[0-9]+([.][0-9]+)?$'
      """)){
      String type=(String)rule.get("alert_type");
      if(!Set.of("PRICE","NAV").contains(type))continue;
      String operator=(String)rule.get("operator");
      if(!Set.of("ABOVE","BELOW","AT_OR_ABOVE","AT_OR_BELOW").contains(operator))continue;
      BigDecimal threshold=new BigDecimal((String)rule.get("threshold"));
      Observation observation="PRICE".equals(type)?price((String)rule.get("target_identifier")):nav((String)rule.get("target_identifier"));
      if(observation==null||!matches(observation.value(),threshold,operator))continue;
      UUID ruleId=(UUID)rule.get("id"),userId=(UUID)rule.get("user_id");
      String bucket=observation.asOf().atZone(ZoneOffset.UTC).toLocalDate().toString();
      String dedupe=ruleId+":"+bucket+":"+operator+":"+threshold.stripTrailingZeros().toPlainString();
      int changed=jdbc.update("""
        INSERT INTO user_notification_history(user_id,alert_rule_id,event_type,title,message,source_code,
          source_reference,occurred_at,details,dedupe_key,delivery_channel,delivery_status)
        VALUES (?,?,?,?,?,?,?,?,jsonb_build_object('value',?::numeric,'threshold',?::numeric,'operator',?,'asOf',?),?,'IN_APP','DELIVERED')
        ON CONFLICT(user_id,dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
        """,userId,ruleId,type+"_ALERT",rule.get("name"),
        rule.get("target_identifier")+" is "+observation.value()+" (rule "+operator+" "+threshold+")",
        observation.source(),observation.reference(),java.sql.Timestamp.from(observation.asOf()),
        observation.value(),threshold,operator,observation.asOf().toString(),dedupe);
      delivered+=changed;
    }
    return delivered;
  }

  private Observation price(String target){
    List<Map<String,Object>> rows=jdbc.queryForList("""
      SELECT q.ltp,q.quoted_at,q.source_code,m.instrument_key FROM upstox_market_quotes q
      JOIN upstox_instrument_map m ON m.instrument_key=q.instrument_key
      WHERE upper(m.instrument_key)=upper(?) OR upper(m.trading_symbol)=upper(?)
        OR upper(m.exchange_code||':'||m.trading_symbol)=upper(?)
      ORDER BY q.quoted_at DESC LIMIT 1
      """,target,target,target);
    if(rows.isEmpty())return null;Map<String,Object> row=rows.get(0);
    return new Observation((BigDecimal)row.get("ltp"),((java.sql.Timestamp)row.get("quoted_at")).toInstant(),(String)row.get("source_code"),(String)row.get("instrument_key"));
  }
  private Observation nav(String target){
    if(target==null||!target.matches("[0-9]{1,18}"))return null;
    List<Map<String,Object>> rows=jdbc.queryForList("SELECT nav,nav_date,source_code FROM mutual_fund_nav WHERE scheme_code=? ORDER BY nav_date DESC LIMIT 1",Long.parseLong(target));
    if(rows.isEmpty())return null;Map<String,Object> row=rows.get(0);LocalDate date=((java.sql.Date)row.get("nav_date")).toLocalDate();
    return new Observation((BigDecimal)row.get("nav"),date.atStartOfDay(ZoneId.of("Asia/Kolkata")).toInstant(),(String)row.get("source_code"),target);
  }
  private boolean matches(BigDecimal value,BigDecimal threshold,String operator){int cmp=value.compareTo(threshold);return switch(operator){case "ABOVE"->cmp>0;case "BELOW"->cmp<0;case "AT_OR_ABOVE"->cmp>=0;case "AT_OR_BELOW"->cmp<=0;default->false;};}
  private record Observation(BigDecimal value,Instant asOf,String source,String reference){}
}
