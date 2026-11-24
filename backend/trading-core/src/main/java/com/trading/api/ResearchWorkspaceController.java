package com.trading.api;

import com.fasterxml.jackson.databind.JsonNode;
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

