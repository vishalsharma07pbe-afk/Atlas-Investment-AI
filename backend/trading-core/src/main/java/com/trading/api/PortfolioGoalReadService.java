package com.trading.api;

import java.time.LocalDate;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import static com.trading.api.PortfolioGoalController.*;

/** Shared owner-local read path for both dashboard and scheduled goal research. */
@Service
public class PortfolioGoalReadService {
  private final JdbcTemplate jdbc;
  public PortfolioGoalReadService(JdbcTemplate jdbc){this.jdbc=jdbc;}
  List<Goal> read(UUID owner,LocalDate today){
    var linked=new HashMap<UUID,List<LinkedHolding>>();
    jdbc.query("""
      SELECT a.goal_id,a.holding_id,a.symbol,a.asset_type,
        CASE WHEN p.id IS NULL THEN 'MISSING_HOLDING'
          WHEN p.quantity<=0 OR p.last_price IS NULL OR p.last_price<0 OR p.price_as_of IS NULL
            OR p.price_as_of>now() OR (now() AT TIME ZONE 'Asia/Kolkata')::date-
              (p.price_as_of AT TIME ZONE 'Asia/Kolkata')::date >
              CASE WHEN p.asset_type='MUTUAL_FUND' THEN 7 ELSE 5 END THEN 'UNAVAILABLE_RECENT_VALUE'
          ELSE 'RECENT_RECORDED' END AS status,
        p.quantity*p.last_price AS recorded_value
      FROM portfolio_goal_holdings a LEFT JOIN personal_holdings p
        ON p.id=a.holding_id AND p.user_id=a.user_id AND p.symbol=a.symbol AND p.asset_type=a.asset_type
      WHERE a.user_id=? ORDER BY a.holding_id
      """,rs->{
        String status=rs.getString("status");
        linked.computeIfAbsent(rs.getObject("goal_id",UUID.class),k->new ArrayList<>()).add(
          new LinkedHolding(rs.getLong("holding_id"),rs.getString("symbol"),rs.getString("asset_type"),status,
            "RECENT_RECORDED".equals(status)?rs.getBigDecimal("recorded_value"):null));
      },owner);
    List<Goal> goals=jdbc.query("""
      SELECT id,name,target_amount,reserved_amount,balance_date,deadline,monthly_contribution
      FROM portfolio_saved_goals WHERE user_id=? ORDER BY deadline,id
      """,(rs,row)->{
        var input=new Input(rs.getString("name"),rs.getBigDecimal("target_amount"),rs.getBigDecimal("reserved_amount"),
          rs.getObject("balance_date",LocalDate.class),rs.getObject("deadline",LocalDate.class),rs.getBigDecimal("monthly_contribution"));
        UUID id=rs.getObject("id",UUID.class);
        var funding=funding(input,linked.getOrDefault(id,List.of()));
        return new Goal(id,input.name(),input.targetAmount(),input.reservedAmount(),
          input.balanceDate(),input.deadline(),input.monthlyContribution(),linkedProgress(input,funding,today),funding);
      },owner);
    return goals;
  }
}
