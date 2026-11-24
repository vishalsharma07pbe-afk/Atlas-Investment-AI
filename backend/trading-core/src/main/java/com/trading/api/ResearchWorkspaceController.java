package com.trading.api;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/research-workspace")
public class ResearchWorkspaceController {
  private final JdbcTemplate jdbc;
  public ResearchWorkspaceController(JdbcTemplate jdbc){this.jdbc=jdbc;}

  public record ScreenerInput(String name,JsonNode definition){}
  public record AlertInput(String name,String alertType,String targetIdentifier,JsonNode condition,Boolean enabled){}
  public record SipPlanInput(Long schemeCode,String schemeName,BigDecimal monthlyAmount,
                             LocalDate startDate,LocalDate nextInstallmentDate,
                             Boolean active,String notes){}

  @GetMapping("/sip-plans")
  public List<Map<String,Object>> sipPlans(){
    return jdbc.queryForList("""
      SELECT id,scheme_code,scheme_name,monthly_amount,start_date,
        next_installment_date,active,notes,created_at,updated_at
      FROM mutual_fund_sip_plans WHERE user_id=?
      ORDER BY active DESC,next_installment_date,scheme_name
      """,AuthSecurity.currentUser());
  }

  @PostMapping("/sip-plans")
  public Map<String,Object> saveSipPlan(@RequestBody SipPlanInput input){
    if(input==null||input.schemeCode()==null||input.schemeCode()<=0)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Choose a valid mutual fund scheme");
    String schemeName=bounded(input.schemeName(),300,"Invalid scheme name");
    if(input.monthlyAmount()==null||input.monthlyAmount().signum()<=0||
       input.monthlyAmount().compareTo(new BigDecimal("100000000"))>0)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid monthly SIP amount");
    LocalDate start=input.startDate()==null?LocalDate.now():input.startDate();
    LocalDate next=input.nextInstallmentDate()==null?start:input.nextInstallmentDate();
    if(next.isBefore(start)||start.isBefore(LocalDate.now().minusYears(1))||
       start.isAfter(LocalDate.now().plusYears(10)))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid SIP dates");
    String notes=input.notes()==null?null:input.notes().trim();
    if(notes!=null&&notes.length()>300)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"SIP notes are too long");
    boolean active=input.active()==null||input.active();
    UUID id=jdbc.queryForObject("""
      INSERT INTO mutual_fund_sip_plans(user_id,scheme_code,scheme_name,monthly_amount,
        start_date,next_installment_date,active,notes)
      VALUES (?,?,?,?,?,?,?,?)
      ON CONFLICT(user_id,scheme_code) DO UPDATE SET
        scheme_name=EXCLUDED.scheme_name,monthly_amount=EXCLUDED.monthly_amount,
        start_date=EXCLUDED.start_date,next_installment_date=EXCLUDED.next_installment_date,
        active=EXCLUDED.active,notes=EXCLUDED.notes,updated_at=now()
      RETURNING id
      """,UUID.class,AuthSecurity.currentUser(),input.schemeCode(),schemeName,
      input.monthlyAmount(),start,next,active,notes);
    return Map.of("saved",true,"id",id,"scheme_code",input.schemeCode());
  }

  @PatchMapping("/sip-plans/{id}/active")
  public Map<String,Boolean> setSipActive(@PathVariable UUID id,@RequestBody Map<String,Boolean> body){
    if(body==null||body.get("active")==null)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Active state is required");
    requireDeleted(jdbc.update("UPDATE mutual_fund_sip_plans SET active=?,updated_at=now() WHERE id=? AND user_id=?",
      body.get("active"),id,AuthSecurity.currentUser()));
    return Map.of("saved",true);
  }

  @DeleteMapping("/sip-plans/{id}")
  public Map<String,Boolean> deleteSipPlan(@PathVariable UUID id){
    requireDeleted(jdbc.update("DELETE FROM mutual_fund_sip_plans WHERE id=? AND user_id=?",id,AuthSecurity.currentUser()));
    return Map.of("deleted",true);
  }

  @GetMapping("/screeners")
  public List<Map<String,Object>> screeners(){
    return jdbc.queryForList("SELECT id,name,definition,created_at,updated_at FROM saved_screeners WHERE user_id=? ORDER BY name",AuthSecurity.currentUser());
  }
  @PostMapping("/screeners")
  public Map<String,Object> saveScreener(@RequestBody ScreenerInput input){
    String name=bounded(input==null?null:input.name(),80,"Invalid screener name");
    JsonNode definition=input.definition();validateJson(definition,16_384);
    UUID id=jdbc.queryForObject("""
      INSERT INTO saved_screeners(user_id,name,definition) VALUES (?,?,?::jsonb)
      ON CONFLICT(user_id,name) DO UPDATE SET definition=EXCLUDED.definition,updated_at=now()
      RETURNING id
      """,UUID.class,AuthSecurity.currentUser(),name,definition.toString());
    return Map.of("saved",true,"id",id,"name",name);
  }
  @DeleteMapping("/screeners/{id}")
  public Map<String,Boolean> deleteScreener(@PathVariable UUID id){
    requireDeleted(jdbc.update("DELETE FROM saved_screeners WHERE id=? AND user_id=?",id,AuthSecurity.currentUser()));
    return Map.of("deleted",true);
  }

  @GetMapping("/watchlist")
  public List<Map<String,Object>> watchlist(){
    return jdbc.queryForList("""
      SELECT i.id instrument_id,e.code exchange,i.symbol,i.series,i.instrument_type,w.created_at
      FROM watchlist_items w JOIN instruments i ON i.id=w.instrument_id
      JOIN exchanges e ON e.id=i.exchange_id WHERE w.user_id=? ORDER BY e.code,i.symbol
      """,AuthSecurity.currentUser());
  }
  @PutMapping("/watchlist/{instrumentId}")
  public Map<String,Object> addWatch(@PathVariable long instrumentId){
    if(instrumentId<=0||jdbc.queryForObject("SELECT count(*) FROM instruments WHERE id=? AND active",Integer.class,instrumentId)==0)
      throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Instrument not found");
    jdbc.update("INSERT INTO watchlist_items(user_id,instrument_id) VALUES (?,?) ON CONFLICT DO NOTHING",AuthSecurity.currentUser(),instrumentId);
    return Map.of("saved",true,"instrument_id",instrumentId);
  }
  @DeleteMapping("/watchlist/{instrumentId}")
  public Map<String,Boolean> removeWatch(@PathVariable long instrumentId){
    requireDeleted(jdbc.update("DELETE FROM watchlist_items WHERE user_id=? AND instrument_id=?",AuthSecurity.currentUser(),instrumentId));
    return Map.of("deleted",true);
  }

  @GetMapping("/alerts")
  public List<Map<String,Object>> alerts(){
    return jdbc.queryForList("SELECT id,name,alert_type,target_identifier,condition,enabled,created_at,updated_at FROM user_alert_rules WHERE user_id=? ORDER BY name",AuthSecurity.currentUser());
  }
  @PostMapping("/alerts")
  public Map<String,Object> saveAlert(@RequestBody AlertInput input){
    String name=bounded(input==null?null:input.name(),100,"Invalid alert name");
    String type=input.alertType()==null?"":input.alertType().trim().toUpperCase(Locale.ROOT);
    if(!Set.of("PRICE","NAV","NEWS","PORTFOLIO_CHANGE").contains(type))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid alert type");
    String target=bounded(input.targetIdentifier(),120,"Invalid alert target");
    validateJson(input.condition(),8_192);
    boolean enabled=input.enabled()==null||input.enabled();
    UUID id=jdbc.queryForObject("""
      INSERT INTO user_alert_rules(user_id,name,alert_type,target_identifier,condition,enabled)
      VALUES (?,?,?,?,?::jsonb,?) ON CONFLICT(user_id,name) DO UPDATE SET
      alert_type=EXCLUDED.alert_type,target_identifier=EXCLUDED.target_identifier,
      condition=EXCLUDED.condition,enabled=EXCLUDED.enabled,updated_at=now() RETURNING id
      """,UUID.class,AuthSecurity.currentUser(),name,type,target,input.condition().toString(),enabled);
    return Map.of("saved",true,"id",id,"name",name);
  }
  @DeleteMapping("/alerts/{id}")
  public Map<String,Boolean> deleteAlert(@PathVariable UUID id){
    requireDeleted(jdbc.update("DELETE FROM user_alert_rules WHERE id=? AND user_id=?",id,AuthSecurity.currentUser()));
    return Map.of("deleted",true);
  }

  @GetMapping("/notifications/summary")
  public Map<String,Object> notificationSummary(){
    Long unread=jdbc.queryForObject("SELECT count(*) FROM user_notification_history WHERE user_id=? AND read_at IS NULL",Long.class,AuthSecurity.currentUser());
    return Map.of("unread_count",unread==null?0L:unread);
  }

  @GetMapping("/notifications")
  public List<Map<String,Object>> notifications(@RequestParam(defaultValue="false") boolean unreadOnly){
    return jdbc.queryForList("""
      SELECT id,alert_rule_id,event_type,title,message,source_code,source_reference,occurred_at,read_at,
      details,delivery_channel,delivery_status
      FROM user_notification_history WHERE user_id=? AND (?=false OR read_at IS NULL)
      ORDER BY occurred_at DESC LIMIT 200
      """,AuthSecurity.currentUser(),unreadOnly);
  }
  @PatchMapping("/notifications/{id}/read")
  public Map<String,Boolean> markRead(@PathVariable UUID id){
    requireDeleted(jdbc.update("UPDATE user_notification_history SET read_at=COALESCE(read_at,now()) WHERE id=? AND user_id=?",id,AuthSecurity.currentUser()));
    return Map.of("read",true);
  }

  private void validateJson(JsonNode value,int max){
    if(value==null||value.isNull()||!value.isObject()||value.toString().length()>max)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid structured definition");
  }
  private String bounded(String raw,int max,String message){
    if(raw==null||raw.trim().isEmpty()||raw.trim().length()>max)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,message);
    return raw.trim();
  }
  private void requireDeleted(int changed){if(changed==0)throw new ResponseStatusException(HttpStatus.NOT_FOUND);}
}

