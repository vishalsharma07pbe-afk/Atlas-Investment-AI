package com.trading.api;

import com.trading.market.MarketCalendarService;
import java.time.*;
import java.time.temporal.TemporalAdjusters;
import java.util.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

/** Scheduled owner-local goal alerts; uses the same valuation and progress model as the dashboard. */
@Service
public class PortfolioGoalNotifications {
  private static final Logger LOG=LoggerFactory.getLogger(PortfolioGoalNotifications.class);
  private final JdbcTemplate jdbc;
  private final PortfolioGoalReadService reader;
  private final TransactionTemplate transaction;
  private UUID cursor;
  @Value("${ATLAS_PORTFOLIO_REVIEW_ENABLED:false}") boolean enabled;
  public PortfolioGoalNotifications(JdbcTemplate jdbc,PortfolioGoalReadService reader,PlatformTransactionManager manager){
    this.jdbc=jdbc;this.reader=reader;
    transaction=new TransactionTemplate(manager);
    transaction.setIsolationLevel(TransactionDefinition.ISOLATION_REPEATABLE_READ);
  }
  @Scheduled(initialDelayString="${atlas.goal.alert.initial-ms:60000}",fixedDelayString="${atlas.goal.alert.poll-ms:300000}")
  public synchronized void scheduled(){
    if(!enabled)return;
    List<UUID> owners=cursor==null?jdbc.queryForList("""
      SELECT DISTINCT user_id FROM portfolio_saved_goals ORDER BY user_id LIMIT 100
      """,UUID.class):jdbc.queryForList("""
      SELECT DISTINCT user_id FROM portfolio_saved_goals WHERE user_id>? ORDER BY user_id LIMIT 100
      """,UUID.class,cursor);
    for(UUID owner:owners)try{evaluateOwner(owner);}catch(DataAccessException ex){
      LOG.warn("Local goal alert evaluation unavailable ({})",ex.getClass().getSimpleName());
    }
    cursor=owners.size()==100?owners.getLast():null;
  }
  record Attention(String kind,String title,String message){}
  static Attention attention(PortfolioGoalController.Goal goal,LocalDate today){
    var p=goal.progress();
    return switch(p.status()){
      case "INCOMPLETE_LINKED_VALUATION" -> new Attention("LINKED_VALUE","Goal valuation needs review","An assigned holding lacks a recent recorded value or is missing. Combined funding is unavailable.");
      case "STALE_RECORDED_BALANCE" -> new Attention("STALE_BALANCE","Goal balance needs an update","The reserved balance is older than 30 days. Forward funding estimates are withheld.");
      case "NO_REMAINING_MONTH_ENDS" -> new Attention("DEADLINE_GAP","Goal deadline funding gap","There are no remaining scheduled month ends and a recorded funding gap remains.");
      case "FUNDING_SHORTFALL" -> new Attention("SHORTFALL","Goal funding shortfall","Planned contributions fall short under unchanged-value assumptions. Review the required monthly amount.");
      case "FUNDED_UNDER_ZERO_GROWTH","RECORDED_TARGET_FUNDED" -> fundedAttention(goal,today);
      default -> null;
    };
  }
  private static Attention fundedAttention(PortfolioGoalController.Goal goal,LocalDate today){
    // Keep the immediate deadline warning ahead of conditional market risk.
    var p=goal.progress();
    if("FUNDED_UNDER_ZERO_GROWTH".equals(p.status())&&!goal.deadline().isAfter(today.plusDays(30))&&
        p.recordedGap()!=null&&p.recordedGap().signum()>0)
      return new Attention("DEADLINE_NEAR","Goal deadline approaching","The deadline is within 30 days and recorded funding is not yet complete. Planned contributions are not confirmed payments.");
    if(p.zeroGrowthShortfall()==null||p.zeroGrowthShortfall().signum()!=0)return null;
    var risk=PortfolioGoalRisk.assess(goal,today);
    if(!"ILLUSTRATIVE_STRESS_AVAILABLE".equals(risk.status()))return null;
    var worst=risk.scenarios().stream().filter(s->s.projectedShortfall().signum()>0)
      .max(Comparator.comparing(PortfolioGoalRisk.Scenario::projectedShortfall)
        .thenComparingInt(s->s.equityDeclinePercent()+s.fundDeclinePercent()));
    if(worst.isEmpty())return null;
    var s=worst.get();
    String shocks=(s.equityDeclinePercent()>0?"direct equity -"+s.equityDeclinePercent()+"%":"")
      +(s.equityDeclinePercent()>0&&s.fundDeclinePercent()>0?", ":"")
      +(s.fundDeclinePercent()>0?"fund NAV -"+s.fundDeclinePercent()+"%":"");
    return new Attention("DOWNSIDE_SHORTFALL","Goal funding vulnerable to downside",
      "Unchanged-value funding meets the target, but the illustrative "+shocks+
      " shock creates a projected shortfall of INR "+s.projectedShortfall().toPlainString()+
      ". This is not a forecast or verified withdrawal value. Planned contributions are not confirmed payments.");
  }
  public int evaluateOwner(UUID owner){
    Integer inserted=transaction.execute(status->{
      LocalDate today=LocalDate.now(MarketCalendarService.IST);
      String week=today.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)).toString();
      int count=0;
      for(var goal:reader.read(owner,today)){
        Attention a=attention(goal,today);
        if(a==null)continue;
        count+=jdbc.update("""
          INSERT INTO user_notification_history(user_id,event_type,title,message,source_code,source_reference,
            occurred_at,details,dedupe_key,delivery_channel,delivery_status)
          SELECT user_id,'PORTFOLIO_RISK',?,?,'ATLAS_GOAL_REVIEW',id::text,now(),
            jsonb_build_object('goal_id',id,'kind',?::text,'status',?::text,'as_of',?::text),
            'goal-review:'||id::text||':'||?::text||':'||?::text,'IN_APP','DELIVERED'
          FROM portfolio_saved_goals WHERE id=? AND user_id=?
          ON CONFLICT DO NOTHING
          """,a.title(),goal.name()+": "+a.message()+" Open My Portfolio for current goal evidence. Not a trade instruction.",
          a.kind(),goal.progress().status(),today.toString(),a.kind(),week,goal.id(),owner);
      }
      return count;
    });
    return inserted==null?0:inserted;
  }
}
